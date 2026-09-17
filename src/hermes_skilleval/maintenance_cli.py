"""Installable maintenance entrypoint. Offline paths never load model libraries."""

from __future__ import annotations
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def recommend(args):
    from hermes_skilleval.runtime_utility import load_registry

    registry, skills = load_registry(args.registry, args.assets)
    start = time.perf_counter()
    result = {
        "arm": args.arm,
        "registry_id": registry["registry_id"],
        "models_loaded": False,
    }
    if args.arm == "N":
        result["skill_ids"] = [s.id for s in skills]
    elif args.arm == "F":
        from hermes_skilleval.fixed_baseline import fixed_ids

        if not args.fixed_config or not args.repository:
            raise ValueError("fixed mode requires --fixed-config and --repository")
        result["skill_ids"] = fixed_ids(
            args.repository, json.loads(args.fixed_config.read_text()), registry
        )
    else:
        if not args.profile or not args.request:
            raise ValueError("strong mode requires --profile and --request")
        from hermes_skilleval.routers.skillrouter_open import (
            OpenProfile,
            SkillRouterOpen,
        )
        from hermes_skilleval.skill_selection import (
            SelectionConfig,
            bind_snapshot,
            select,
        )

        profile = json.loads(args.profile.read_text())
        for key in ("encoder_path", "reranker_path"):
            path = Path(profile[key])
            profile[key] = (
                path
                if path.is_absolute()
                else (args.profile.resolve().parent / path).resolve()
            )
        router = SkillRouterOpen(
            profile=OpenProfile(**profile.pop("profile", {})), **profile
        )
        constructor = time.perf_counter() - start
        router.index(
            [asdict(s) for s in skills], args.cache, registry_id=registry["registry_id"]
        )
        prompt = args.request.read_text()
        result = bind_snapshot(
            router.recommend(prompt, 2), prompt, registry["registry_id"]
        )
        selection = select(
            prompt=prompt,
            snapshot=result,
            registry=registry,
            policy="topk",
            k=2,
            config=SelectionConfig(),
        )
        result.update(
            selection=selection,
            skill_ids=selection["skill_ids"],
            models_loaded=True,
            arm="S",
        )
        result["timing"]["constructor_seconds"] = constructor
    result["recommend_wall_seconds"] = time.perf_counter() - start
    if args.output:
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
    print(
        json.dumps(
            result
            if args.arm != "S"
            else {
                k: result[k]
                for k in ["arm", "skill_ids", "timing", "recommend_wall_seconds"]
            },
            indent=2,
        )
    )


def main():
    if len(sys.argv) > 2 and sys.argv[1:3] == ["advisory-study", "records"]:
        from .repo_routing.advisory_records import main as records_main

        return records_main(sys.argv[3:])
    if len(sys.argv) > 1 and sys.argv[1] == "advisory-study":
        from .repo_routing.advisory_study import main as advisory_main

        return advisory_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "support":
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "hermes_skilleval.repo_routing.support_cli",
                *sys.argv[2:],
            ]
        )
    commands = {
        "run": "execute",
        "qualify": "qualify",
        "verify": "verify_patch",
        "canary": "canary",
        "prepare": "prepare_spec",
    }
    if len(sys.argv) > 1 and sys.argv[1] in commands:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "hermes_skilleval._maintenance." + commands[sys.argv[1]],
                *sys.argv[2:],
            ]
        )
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in commands:
        sub.add_parser(command, help="Shared isolated " + command + " entrypoint")
    sub.add_parser(
        "support", help="Experimental text support scoring/calibration/checks"
    )
    assist = sub.add_parser(
        "assist", help="Current-task isolated patch; no gold or qualification"
    )
    for name in (
        "repo",
        "request",
        "repository-config",
        "checks",
        "registry",
        "skill-assets",
        "output",
    ):
        assist.add_argument("--" + name, type=Path, required=True)
    assist.add_argument(
        "--policy", choices=["native", "fixed", "strong", "repo-aware", "auto"]
    )
    assist.add_argument("--routing-config", type=Path)
    assist.add_argument("--fixed-config", type=Path)
    assist.add_argument("--arm", choices=["N", "F"], default="N")
    assist.add_argument("--model", default="gpt-5.6-sol")
    assist.add_argument(
        "--effort", choices=["low", "medium", "high", "xhigh", "max"], default="medium"
    )
    assist.add_argument("--timeout", type=int, default=600)
    assist.add_argument(
        "--plan-only",
        action="store_true",
        help="Inspect inputs/resources without model calls or source writes",
    )
    route_parser = sub.add_parser(
        "route", help="Experimental sourced repository routing"
    )
    for name in (
        "repo",
        "request",
        "registry",
        "skill-assets",
        "routing-config",
        "output",
    ):
        route_parser.add_argument("--" + name, type=Path, required=True)
    route_parser.add_argument(
        "--policy",
        choices=["native", "fixed", "strong", "repo-aware", "auto"],
        required=True,
    )
    records = sub.add_parser("records", help="Recompute public records offline")
    records.add_argument("--index", type=Path, required=True)
    records.add_argument("--output", type=Path, required=True)
    doctor = sub.add_parser("doctor", help="No model calls or downloads")
    doctor.add_argument("--profile", type=Path)
    rec = sub.add_parser("recommend")
    rec.add_argument("--arm", choices=["N", "F", "S"], required=True)
    for name in ["registry", "assets"]:
        rec.add_argument("--" + name, type=Path, required=True)
    for name in ["fixed-config", "profile", "request", "cache", "output"]:
        rec.add_argument("--" + name, type=Path)
    rec.add_argument("--repository")
    args = parser.parse_args()
    if args.command == "route":
        from hermes_skilleval.repo_routing.policy import route, read_config
        from hermes_skilleval.runtime_utility import load_registry

        registry, _ = load_registry(args.registry, args.skill_assets)
        result = route(
            args.repo,
            args.request.read_text(),
            {"network": "unknown", "python": sys.version.split()[0]},
            registry,
            args.policy,
            read_config(args.routing_config),
        )
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
        print(
            json.dumps(
                {k: result[k] for k in ("action", "skill_ids", "calls", "timing")},
                indent=2,
            )
        )
        return 0
    if args.command == "assist":
        from hermes_skilleval._maintenance.assist import execute

        try:
            result, code = execute(args)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            print(
                json.dumps(
                    {
                        "status": "PREFLIGHT_REJECTED",
                        "error": str(exc),
                        "resolved": None,
                    }
                )
            )
            return 2
        print(json.dumps(result, indent=2))
        return code
    if args.command == "records":
        from hermes_skilleval.maintenance_records import recompute

        print(json.dumps(recompute(args.index, args.output)["summary"], indent=2))
    elif args.command == "doctor":
        from hermes_skilleval.repository_profile import CSVKIT, SQLITE_UTILS
        from hermes_skilleval._maintenance.assist import CSV_DIFF

        result = {
            "models_loaded": False,
            "native_fixed_requires_retrieval": False,
            "python": sys.version.split()[0],
            "docker_executable": bool(shutil.which("docker")),
            "profiles": [p.to_dict() for p in [SQLITE_UTILS, CSVKIT, CSV_DIFF]],
            "strong": {"configured": bool(args.profile), "available": False},
        }
        if args.profile:
            config = json.loads(args.profile.read_text())
            present = {}
            for key in ["encoder_path", "reranker_path"]:
                path = Path(config[key])
                path = (
                    path if path.is_absolute() else args.profile.resolve().parent / path
                )
                present[key] = path.is_dir() and bool(list(path.glob("*.safetensors")))
            result["strong"].update(
                assets_present=present,
                dependencies_present={
                    k: importlib.util.find_spec(k) is not None
                    for k in ["torch", "transformers"]
                },
                available=False,
                note="Presence only; inference has not been tested by doctor",
            )
        print(json.dumps(result, indent=2))
    else:
        recommend(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
