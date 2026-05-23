from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from hermes_skilleval.comparison import write_comparison_report
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
from hermes_skilleval.routers.embedding import EmbeddingRouter
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.routers.keyword import KeywordRouter
from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.storage import ensure_dir
from hermes_skilleval.task_loader import load_tasks


ROUTER_NAMES = ("keyword", "hybrid", "embedding")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    try:
        args.handler(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
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
    compare_parser.add_argument("--top-k", type=int, default=5)
    compare_parser.add_argument("--output-dir", default="runs/comparison")
    compare_parser.set_defaults(handler=_run_compare)

    report_parser = subparsers.add_parser("report", help="write a markdown run report")
    report_parser.add_argument("--runs", required=True)
    report_parser.set_defaults(handler=_run_report)

    return parser


def _run_index(args: argparse.Namespace) -> None:
    skills = scan_skills(args.skills_path)
    save_skill_index(skills, args.output)
    print(f"Indexed {len(skills)} skills to {args.output}")


def _run_eval(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    skills = load_skill_index(args.index)
    tasks = load_tasks(args.tasks)
    router = _router(args.router)
    output_dir = ensure_dir(args.output_dir)
    results_path = _write_eval_results(tasks, skills, router, args.top_k, output_dir)

    print(f"Wrote {len(tasks)} results to {results_path}")


def _run_compare(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    router_names = _parse_router_names(args.routers)
    skills = load_skill_index(args.index)
    tasks = load_tasks(args.tasks)
    output_dir = ensure_dir(args.output_dir)
    result_paths = {}
    for router_name in router_names:
        router = _router(router_name)
        router_dir = ensure_dir(output_dir / router_name)
        result_paths[router_name] = _write_eval_results(
            tasks,
            skills,
            router,
            args.top_k,
            router_dir,
        )
        write_markdown_report(result_paths[router_name], router_dir / "report.md")
    comparison_path = output_dir / "comparison.md"
    write_comparison_report(result_paths, comparison_path)

    print(f"Wrote comparison report to {comparison_path}")


def _write_eval_results(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    router: SkillRouter,
    top_k: int,
    output_dir: Path,
) -> Path:
    results_path = output_dir / "results.jsonl"

    with results_path.open("w", encoding="utf-8") as file:
        for task in tasks:
            result = router.route(task, skills, top_k)
            file.write(json.dumps(_result_record(task, result), sort_keys=True) + "\n")

    return results_path


def _run_report(args: argparse.Namespace) -> None:
    run_dir = Path(args.runs)
    results_path = run_dir / "results.jsonl"
    report_path = run_dir / "report.md"
    write_markdown_report(results_path, report_path)
    print(f"Wrote report to {report_path}")


def _router(name: str) -> SkillRouter:
    if name == "keyword":
        return KeywordRouter()
    if name == "hybrid":
        return HybridRouter()
    if name == "embedding":
        return EmbeddingRouter()
    raise ValueError(f"unknown router: {name}")


def _parse_router_names(value: str) -> list[str]:
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError("--routers must include at least one router")
    unknown = sorted(set(names) - set(ROUTER_NAMES))
    if unknown:
        raise ValueError(f"unknown router(s): {', '.join(unknown)}")
    return names


def _result_record(task: BenchmarkTask, result: RouteResult) -> dict[str, object]:
    selected = result.selected_skill_ids
    gold = task.gold_skills
    negative = task.negative_skills
    return {
        "task_id": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "router": result.router,
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
