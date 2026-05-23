from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from hermes_skilleval.comparison import write_comparison_report
from hermes_skilleval.failure_analysis import (
    result_paths_from_comparison_dir,
    write_failure_analysis_report,
)
from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.report import write_markdown_report
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.embedding import (
    EmbeddingDependencyError,
    EmbeddingRouter,
    HashingEmbeddingModel,
    SentenceTransformerEmbeddingModel,
)
from hermes_skilleval.routers.gated import VerificationGatedRouter
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.routers.keyword import KeywordRouter
from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.storage import ensure_dir
from hermes_skilleval.task_loader import load_tasks


ROUTER_NAMES = ("keyword", "hybrid", "embedding", "gated")
EMBEDDING_BACKENDS = ("hashing", "sentence-transformers")
ROUTER_LABEL_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class RouterSpec:
    label: str
    router_name: str
    embedding_backend: str | None = None


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    try:
        args.handler(args)
    except (
        EmbeddingDependencyError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skilleval")
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index", help="scan skills and write an index")
    index_parser.add_argument("--skills-path", required=True)
    index_parser.add_argument("--output", default="index/skills.json")
    index_parser.set_defaults(handler=_run_index)

    eval_parser = subparsers.add_parser("eval", help="evaluate a router against tasks")
    eval_parser.add_argument("--index", required=True)
    eval_parser.add_argument("--tasks", required=True)
    eval_parser.add_argument("--router", choices=ROUTER_NAMES, default="keyword")
    _add_embedding_args(eval_parser)
    _add_gated_args(eval_parser)
    eval_parser.add_argument("--top-k", type=int, default=5)
    eval_parser.add_argument("--output-dir", default="runs/latest")
    eval_parser.set_defaults(handler=_run_eval)

    compare_parser = subparsers.add_parser("compare", help="compare multiple routers")
    compare_parser.add_argument("--index", required=True)
    compare_parser.add_argument("--tasks", required=True)
    compare_parser.add_argument(
        "--routers",
        default="keyword,hybrid,embedding",
        help="comma-separated router names",
    )
    _add_embedding_args(compare_parser)
    _add_gated_args(compare_parser)
    compare_parser.add_argument("--top-k", type=int, default=5)
    compare_parser.add_argument("--output-dir", default="runs/comparison")
    compare_parser.set_defaults(handler=_run_compare)

    report_parser = subparsers.add_parser("report", help="write a markdown run report")
    report_parser.add_argument("--runs", required=True)
    report_parser.set_defaults(handler=_run_report)

    failures_parser = subparsers.add_parser(
        "analyze-failures",
        help="write a markdown failure analysis for a comparison run",
    )
    failures_parser.add_argument("--runs", required=True)
    failures_parser.add_argument("--output", default=None)
    failures_parser.add_argument("--baseline", default=None)
    failures_parser.add_argument("--candidate", default=None)
    failures_parser.set_defaults(handler=_run_analyze_failures)

    return parser


def _add_embedding_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--embedding-backend",
        choices=EMBEDDING_BACKENDS,
        default="hashing",
        help="backend used when router is embedding or gated",
    )
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="sentence-transformers model name",
    )
    parser.add_argument(
        "--embedding-cache",
        default=None,
        help="optional JSON cache path for skill embeddings",
    )


def _add_gated_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--gated-pool-size",
        type=int,
        default=10,
        help="candidate pool size reranked by the gated router",
    )


def _run_index(args: argparse.Namespace) -> None:
    skills = scan_skills(args.skills_path)
    save_skill_index(skills, args.output)
    print(f"Indexed {len(skills)} skills to {args.output}")


def _run_eval(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    skills = load_skill_index(args.index)
    tasks = load_tasks(args.tasks)
    router = _router(args.router, args)
    output_dir = ensure_dir(args.output_dir)
    results_path = _write_eval_results(tasks, skills, router, args.top_k, output_dir)

    print(f"Wrote {len(tasks)} results to {results_path}")


def _run_compare(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    router_specs = _parse_router_specs(args.routers)
    skills = load_skill_index(args.index)
    tasks = load_tasks(args.tasks)
    output_dir = ensure_dir(args.output_dir)
    result_paths = {}
    for spec in router_specs:
        router_args = _args_for_router_spec(args, spec)
        router = _router(spec.router_name, router_args)
        router_dir = ensure_dir(output_dir / spec.label)
        result_paths[spec.label] = _write_eval_results(
            tasks,
            skills,
            router,
            args.top_k,
            router_dir,
            router_label=spec.label,
        )
        write_markdown_report(result_paths[spec.label], router_dir / "report.md")
    comparison_path = output_dir / "comparison.md"
    write_comparison_report(result_paths, comparison_path)

    print(f"Wrote comparison report to {comparison_path}")


def _write_eval_results(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    router: SkillRouter,
    top_k: int,
    output_dir: Path,
    router_label: str | None = None,
) -> Path:
    results_path = output_dir / "results.jsonl"

    with results_path.open("w", encoding="utf-8") as file:
        for task in tasks:
            result = router.route(task, skills, top_k)
            file.write(
                json.dumps(
                    _result_record(task, result, router_label=router_label),
                    sort_keys=True,
                )
                + "\n"
            )

    return results_path


def _run_report(args: argparse.Namespace) -> None:
    run_dir = Path(args.runs)
    results_path = run_dir / "results.jsonl"
    report_path = run_dir / "report.md"
    write_markdown_report(results_path, report_path)
    print(f"Wrote report to {report_path}")


def _run_analyze_failures(args: argparse.Namespace) -> None:
    run_dir = Path(args.runs)
    output_path = Path(args.output) if args.output else run_dir / "failure-analysis.md"
    write_failure_analysis_report(
        result_paths_from_comparison_dir(run_dir),
        output_path,
        baseline=args.baseline,
        candidate=args.candidate,
    )
    print(f"Wrote failure analysis to {output_path}")


def _router(name: str, args: argparse.Namespace | None = None) -> SkillRouter:
    if name == "keyword":
        return KeywordRouter()
    if name == "hybrid":
        return HybridRouter()
    if name == "embedding":
        return _embedding_router(args)
    if name == "gated":
        return _gated_router(args)
    raise ValueError(f"unknown router: {name}")


def _embedding_router(args: argparse.Namespace | None) -> EmbeddingRouter:
    backend = getattr(args, "embedding_backend", "hashing")
    cache_path = getattr(args, "embedding_cache", None)
    if backend == "hashing":
        return EmbeddingRouter(model=HashingEmbeddingModel(), cache_path=cache_path)
    if backend == "sentence-transformers":
        model_name = getattr(
            args,
            "embedding_model",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        return EmbeddingRouter(
            model=SentenceTransformerEmbeddingModel(model_name),
            cache_path=cache_path,
        )
    raise ValueError(f"unknown embedding backend: {backend}")


def _gated_router(args: argparse.Namespace | None) -> VerificationGatedRouter:
    candidate_pool_size = getattr(args, "gated_pool_size", 10)
    return VerificationGatedRouter(
        base_router=_embedding_router(args),
        candidate_pool_size=candidate_pool_size,
    )


def _parse_router_names(value: str) -> list[str]:
    return [spec.router_name for spec in _parse_router_specs(value)]


def _parse_router_specs(value: str) -> list[RouterSpec]:
    raw_specs = [name.strip() for name in value.split(",") if name.strip()]
    if not raw_specs:
        raise ValueError("--routers must include at least one router")
    specs = [_parse_router_spec(raw_spec) for raw_spec in raw_specs]
    duplicate_labels = sorted(
        label
        for label in {spec.label for spec in specs}
        if _count_labels(specs, label) > 1
    )
    if duplicate_labels:
        raise ValueError(f"duplicate router label(s): {', '.join(duplicate_labels)}")
    return specs


def _parse_router_spec(value: str) -> RouterSpec:
    label: str | None = None
    target = value
    if "=" in value:
        label, target = [part.strip() for part in value.split("=", maxsplit=1)]
        if not label:
            raise ValueError("router label must not be empty")

    router_name, _, embedding_backend = target.partition(":")
    router_name = router_name.strip()
    embedding_backend = embedding_backend.strip() or None
    if router_name not in ROUTER_NAMES:
        raise ValueError(f"unknown router(s): {router_name}")
    if embedding_backend is not None:
        if router_name not in ("embedding", "gated"):
            raise ValueError(
                "only embedding or gated router specs can include a backend"
            )
        if embedding_backend not in EMBEDDING_BACKENDS:
            raise ValueError(f"unknown embedding backend: {embedding_backend}")

    label = label or _default_router_label(router_name, embedding_backend)
    if not ROUTER_LABEL_RE.match(label):
        raise ValueError(
            "router labels may only contain letters, numbers, dots, underscores, and hyphens"
        )
    return RouterSpec(
        label=label,
        router_name=router_name,
        embedding_backend=embedding_backend,
    )


def _count_labels(specs: list[RouterSpec], label: str) -> int:
    return sum(1 for spec in specs if spec.label == label)


def _default_router_label(router_name: str, embedding_backend: str | None) -> str:
    if router_name in ("embedding", "gated") and embedding_backend is not None:
        return f"{router_name}-{embedding_backend}"
    return router_name


def _args_for_router_spec(
    args: argparse.Namespace,
    spec: RouterSpec,
) -> argparse.Namespace:
    if spec.embedding_backend is None:
        return args
    router_args = argparse.Namespace(**vars(args))
    router_args.embedding_backend = spec.embedding_backend
    return router_args


def _result_record(
    task: BenchmarkTask,
    result: RouteResult,
    router_label: str | None = None,
) -> dict[str, object]:
    selected = result.selected_skill_ids
    gold = task.gold_skills
    negative = task.negative_skills
    return {
        "task_id": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "router": router_label or result.router,
        "selected_skill_ids": selected,
        "scores": result.scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": result.latency_ms,
        "recall_at_1": recall_at_k(selected, gold, 1),
        "recall_at_3": recall_at_k(selected, gold, 3),
        "recall_at_5": recall_at_k(selected, gold, 5),
        "precision_at_5": precision_at_k(selected, gold, 5),
        "mrr": mean_reciprocal_rank(selected, gold),
        "ndcg_at_5": ndcg_at_k(selected, gold, 5),
        "negative_hit_rate": negative_hit_rate(selected, negative, 5),
    }


if __name__ == "__main__":
    raise SystemExit(main())
