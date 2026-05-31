from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from hermes_skilleval.agent_judge import judge_agent_loop
from hermes_skilleval.agent_loop import run_agent_loop
from hermes_skilleval.blind_validation import write_blind_validation_summary
from hermes_skilleval.calibration import (
    apply_cross_encoder_calibration,
    fit_cross_encoder_calibration,
    read_cross_encoder_calibration,
    write_cross_encoder_calibration,
)
from hermes_skilleval.comparison import write_comparison_report
from hermes_skilleval.dashboard import write_dashboard
from hermes_skilleval.embedding_training import (
    export_embedding_training_pairs,
    write_training_pairs,
)
from hermes_skilleval.failure_analysis import (
    result_paths_from_comparison_dir,
    write_failure_analysis_report,
)
from hermes_skilleval.finetuned_eval import write_finetuned_eval_summary
from hermes_skilleval.metrics import (
    abstention_rate,
    accepted_count,
    accepted_recall_at_k,
    coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_accepted_rate,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
    selection_rate_at_k,
)
from hermes_skilleval.model_manifest import write_model_manifest
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.provenance import write_finetuned_provenance_pack
from hermes_skilleval.release_checks import write_release_check_summary
from hermes_skilleval.release_manifest import write_release_manifest
from hermes_skilleval.release_selector import (
    DEFAULT_RELEASE_POLICY,
    write_release_decision,
)
from hermes_skilleval.report import write_markdown_report
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.cross_encoder import (
    CrossEncoderReranker,
    SentenceTransformerCrossEncoderModel,
)
from hermes_skilleval.routers.embedding import (
    EmbeddingDependencyError,
    EmbeddingRouter,
    HashingEmbeddingModel,
    SentenceTransformerEmbeddingModel,
)
from hermes_skilleval.routers.gated import VerificationGatedRouter
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.routers.keyword import KeywordRouter
from hermes_skilleval.self_improvement import (
    apply_skill_patches,
    propose_skill_patches,
    write_acceptance_report,
    write_patch_report,
    write_patches_json,
)
from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_patch_simulation import (
    read_ranked_patches,
    simulate_skill_patches,
)
from hermes_skilleval.skill_patch_ranking import rank_skill_patches
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.storage import ensure_dir
from hermes_skilleval.task_loader import load_tasks


ROUTER_NAMES = ("keyword", "hybrid", "embedding", "gated", "cross-encoder")
EMBEDDING_BACKENDS = ("hashing", "sentence-transformers")
RERANKER_BACKENDS = ("sentence-transformers",)
ROUTER_LABEL_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DEFAULT_RELEASE_ROOTS = (
    "README.md",
    "docs/phase16.md",
    "docs/phase17.md",
    "docs/phase18.md",
    "docs/release-handoff.md",
    "docs/demo/phase16-blind-validation",
    "docs/demo/phase17-calibrated-release-selector",
    "docs/demo/phase18-ci-release-reproducibility",
)
DEFAULT_RELEASE_REQUIRED_PATHS = (
    "docs/demo/phase16-blind-validation/regression-summary.json",
    "docs/demo/phase16-blind-validation/route-diffs.jsonl",
    "docs/demo/phase17-calibrated-release-selector/release-decision.json",
    "docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.json",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.md",
    "docs/phase17.md",
    "docs/phase18.md",
    "docs/release-handoff.md",
)


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
    _add_cross_encoder_args(eval_parser)
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
    _add_cross_encoder_args(compare_parser)
    compare_parser.add_argument("--top-k", type=int, default=5)
    compare_parser.add_argument("--output-dir", default="runs/comparison")
    compare_parser.set_defaults(handler=_run_compare)

    report_parser = subparsers.add_parser("report", help="write a markdown run report")
    report_parser.add_argument("--runs", required=True)
    report_parser.set_defaults(handler=_run_report)

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="write a self-contained HTML dashboard for router run results",
    )
    dashboard_parser.add_argument("--runs", required=True)
    dashboard_parser.add_argument("--output", required=True)
    dashboard_parser.set_defaults(handler=_run_dashboard)

    agent_loop_parser = subparsers.add_parser(
        "run-agent-loop",
        help="write deterministic agent-in-the-loop traces from router results",
    )
    agent_loop_parser.add_argument("--routes", required=True)
    agent_loop_parser.add_argument("--tasks", required=True)
    agent_loop_parser.add_argument("--skills-index", required=True)
    agent_loop_parser.add_argument("--output-dir", required=True)
    agent_loop_parser.add_argument(
        "--condition",
        choices=("no-skill", "routed-skill", "oracle-skill"),
        default="routed-skill",
    )
    agent_loop_parser.add_argument("--run-label", default=None)
    agent_loop_parser.set_defaults(handler=_run_agent_loop)

    judge_loop_parser = subparsers.add_parser(
        "judge-agent-loop",
        help="judge Phase 10 agent-loop traces with a deterministic evidence rubric",
    )
    judge_loop_parser.add_argument("--traces", required=True)
    judge_loop_parser.add_argument("--output-dir", required=True)
    judge_loop_parser.add_argument("--run-label", default="judge-agent-loop")
    judge_loop_parser.add_argument(
        "--backend",
        choices=("deterministic-rubric",),
        default="deterministic-rubric",
    )
    judge_loop_parser.set_defaults(handler=_run_judge_agent_loop)

    failures_parser = subparsers.add_parser(
        "analyze-failures",
        help="write a markdown failure analysis for a comparison run",
    )
    failures_parser.add_argument("--runs", required=True)
    failures_parser.add_argument("--output", default=None)
    failures_parser.add_argument("--baseline", default=None)
    failures_parser.add_argument("--candidate", default=None)
    failures_parser.set_defaults(handler=_run_analyze_failures)

    improve_parser = subparsers.add_parser(
        "improve-skills",
        help="propose skill metadata patches from failed routing records",
    )
    improve_parser.add_argument("--runs", required=True)
    improve_parser.add_argument("--router", required=True)
    improve_parser.add_argument("--index", required=True)
    improve_parser.add_argument("--tasks", required=True)
    improve_parser.add_argument("--output", required=True)
    improve_parser.add_argument("--patched-index", default=None)
    improve_parser.add_argument("--report", default=None)
    improve_parser.set_defaults(handler=_run_improve_skills)

    judge_parser = subparsers.add_parser(
        "judge-improvement",
        help="accept or reject a patched skill run against a baseline run",
    )
    judge_parser.add_argument("--runs", required=True)
    judge_parser.add_argument("--baseline", required=True)
    judge_parser.add_argument("--candidate", required=True)
    judge_parser.add_argument("--output", required=True)
    judge_parser.set_defaults(handler=_run_judge_improvement)

    rank_patches_parser = subparsers.add_parser(
        "rank-skill-patches",
        help="rank offline metadata patch candidates from failed agent-loop judge records",
    )
    rank_patches_parser.add_argument("--judge-results", required=True)
    rank_patches_parser.add_argument("--routes", required=True)
    rank_patches_parser.add_argument("--tasks", required=True)
    rank_patches_parser.add_argument("--skills-index", required=True)
    rank_patches_parser.add_argument("--output-dir", required=True)
    rank_patches_parser.set_defaults(handler=_run_rank_skill_patches)

    simulate_patches_parser = subparsers.add_parser(
        "simulate-skill-patches",
        help=(
            "apply ranked metadata patches to a shadow skill index and check "
            "route regressions"
        ),
    )
    simulate_patches_parser.add_argument("--ranked-patches", required=True)
    simulate_patches_parser.add_argument("--baseline-routes", required=True)
    simulate_patches_parser.add_argument("--tasks", required=True)
    simulate_patches_parser.add_argument("--skills-index", required=True)
    simulate_patches_parser.add_argument(
        "--router",
        choices=ROUTER_NAMES,
        default="hybrid",
    )
    _add_embedding_args(simulate_patches_parser)
    _add_gated_args(simulate_patches_parser)
    _add_cross_encoder_args(simulate_patches_parser)
    simulate_patches_parser.add_argument("--top-k", type=int, default=5)
    simulate_patches_parser.add_argument("--max-patches", type=int, default=5)
    simulate_patches_parser.add_argument("--output-dir", required=True)
    simulate_patches_parser.set_defaults(handler=_run_simulate_skill_patches)

    export_training_parser = subparsers.add_parser(
        "export-embedding-training-data",
        help="export task-skill pairs for supervised embedding-router training",
    )
    export_training_parser.add_argument("--tasks", required=True)
    export_training_parser.add_argument("--skills-index", required=True)
    export_training_parser.add_argument("--output-dir", required=True)
    export_training_parser.set_defaults(handler=_run_export_embedding_training_data)

    judge_finetuned_parser = subparsers.add_parser(
        "judge-finetuned-embedding",
        help="compare fine-tuned embedding results against a baseline embedding run",
    )
    judge_finetuned_parser.add_argument("--baseline-results", required=True)
    judge_finetuned_parser.add_argument("--candidate-results", required=True)
    judge_finetuned_parser.add_argument("--output-dir", required=True)
    judge_finetuned_parser.add_argument("--baseline-router", default="embedding-minilm")
    judge_finetuned_parser.add_argument(
        "--candidate-router",
        default="finetuned-embedding",
    )
    judge_finetuned_parser.add_argument("--model-dir", required=True)
    judge_finetuned_parser.add_argument(
        "--apply-split",
        choices=("dev", "test", "all"),
        default="all",
    )
    judge_finetuned_parser.add_argument(
        "--write-filtered-results",
        action="store_true",
    )
    judge_finetuned_parser.set_defaults(handler=_run_judge_finetuned_embedding)

    blind_validation_parser = subparsers.add_parser(
        "write-blind-validation",
        help="write a Phase 16 blind validation summary from baseline and candidate results",
    )
    blind_validation_parser.add_argument("--baseline-results", required=True)
    blind_validation_parser.add_argument("--candidate-results", required=True)
    blind_validation_parser.add_argument("--output-dir", required=True)
    blind_validation_parser.add_argument("--baseline-router", default="baseline-minilm")
    blind_validation_parser.add_argument(
        "--candidate-router",
        default="finetuned-embedding",
    )
    blind_validation_parser.add_argument("--model-dir", required=True)
    blind_validation_parser.add_argument("--task-root", required=True)
    blind_validation_parser.set_defaults(handler=_run_write_blind_validation)

    verify_release_parser = subparsers.add_parser(
        "verify-release",
        help="scan public artifacts for required files, secrets, checkpoints, and overclaims",
    )
    verify_release_parser.add_argument("--public-root", action="append", required=True)
    verify_release_parser.add_argument("--required-path", action="append", default=[])
    verify_release_parser.add_argument("--summary-output", required=True)
    verify_release_parser.set_defaults(handler=_run_verify_release)

    release_selector_parser = subparsers.add_parser(
        "select-release-router",
        help="select the default router from Phase 16 blind-validation artifacts",
    )
    release_selector_parser.add_argument("--regression-summary", required=True)
    release_selector_parser.add_argument("--route-diffs", required=True)
    release_selector_parser.add_argument("--output-dir", required=True)
    release_selector_parser.add_argument(
        "--max-regressions",
        type=int,
        default=DEFAULT_RELEASE_POLICY["max_regressions"],
    )
    release_selector_parser.add_argument(
        "--max-negative-hit-delta",
        type=float,
        default=DEFAULT_RELEASE_POLICY["max_negative_hit_delta"],
    )
    release_selector_parser.add_argument(
        "--max-negative-accepted-delta",
        type=float,
        default=DEFAULT_RELEASE_POLICY["max_negative_accepted_delta"],
    )
    release_selector_parser.add_argument(
        "--min-recall-at-5-delta",
        type=float,
        default=DEFAULT_RELEASE_POLICY["min_recall_at_5_delta"],
    )
    release_selector_parser.add_argument(
        "--min-mrr-delta",
        type=float,
        default=DEFAULT_RELEASE_POLICY["min_mrr_delta"],
    )
    release_selector_parser.add_argument(
        "--min-ndcg-at-5-delta",
        type=float,
        default=DEFAULT_RELEASE_POLICY["min_ndcg_at_5_delta"],
    )
    release_selector_parser.set_defaults(handler=_run_select_release_router)

    release_check_parser = subparsers.add_parser(
        "release-check",
        help="rerun release selection and write a reproducibility manifest",
    )
    release_check_parser.add_argument(
        "--regression-summary",
        default="docs/demo/phase16-blind-validation/regression-summary.json",
    )
    release_check_parser.add_argument(
        "--route-diffs",
        default="docs/demo/phase16-blind-validation/route-diffs.jsonl",
    )
    release_check_parser.add_argument(
        "--phase17-output-dir",
        default="docs/demo/phase17-calibrated-release-selector",
    )
    release_check_parser.add_argument(
        "--release-output-dir",
        default="docs/demo/phase18-ci-release-reproducibility",
    )
    release_check_parser.add_argument("--public-root", action="append", default=None)
    release_check_parser.add_argument("--required-path", action="append", default=None)
    release_check_parser.set_defaults(handler=_run_release_check)

    manifest_parser = subparsers.add_parser(
        "write-model-manifest",
        help="write a sanitized file manifest for a remote model directory",
    )
    manifest_parser.add_argument("--model-dir", required=True)
    manifest_parser.add_argument("--local-model-dir", default=None)
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.set_defaults(handler=_run_write_model_manifest)

    provenance_parser = subparsers.add_parser(
        "write-finetuned-provenance",
        help="write a sanitized provenance pack for held-out fine-tuned evidence",
    )
    provenance_parser.add_argument("--training-summary", required=True)
    provenance_parser.add_argument("--train-config", required=True)
    provenance_parser.add_argument("--train-run-summary", required=True)
    provenance_parser.add_argument("--model-manifest", required=True)
    provenance_parser.add_argument("--regression-summary", required=True)
    provenance_parser.add_argument("--output-dir", required=True)
    provenance_parser.set_defaults(handler=_run_write_finetuned_provenance)

    calibrate_parser = subparsers.add_parser(
        "calibrate-cross-encoder",
        help="fit score and margin thresholds from cross-encoder rank-only results",
    )
    calibrate_parser.add_argument("--results", required=True)
    calibrate_parser.add_argument("--output", required=True)
    calibrate_parser.add_argument("--calibrated-output", default=None)
    calibrate_parser.add_argument("--fit-split", choices=("dev", "test"), default="dev")
    calibrate_parser.add_argument(
        "--apply-split",
        choices=("dev", "test", "all"),
        default="test",
    )
    calibrate_parser.add_argument("--top-k", type=int, default=5)
    calibrate_parser.add_argument("--max-negative-hit-rate", type=float, default=0.05)
    calibrate_parser.add_argument(
        "--max-selection-rate-at-5",
        type=float,
        default=1.0,
        help="maximum mean Selection Rate@5 allowed on the fit split",
    )
    calibrate_parser.add_argument(
        "--router-label",
        default="cross-encoder-calibrated",
    )
    calibrate_parser.set_defaults(handler=_run_calibrate_cross_encoder)

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
    parser.add_argument(
        "--selective",
        action="store_true",
        help="allow the gated router to return fewer than top-k skills",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="minimum normalized confidence for selective gated routing",
    )
    parser.add_argument(
        "--contrastive-selective",
        action="store_true",
        help="apply ambiguity-aware selective gating to same-category candidates",
    )
    parser.add_argument(
        "--contrastive-margin",
        type=float,
        default=6.0,
        help="maximum evidence gap allowed for contrastive same-category acceptance",
    )
    parser.add_argument(
        "--min-evidence",
        type=float,
        default=2.0,
        help="minimum prompt evidence for non-first same-category candidates",
    )


def _add_cross_encoder_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cross-encoder-model",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="sentence-transformers CrossEncoder model name or local path",
    )
    parser.add_argument(
        "--cross-encoder-batch-size",
        type=int,
        default=16,
        help="batch size for cross-encoder pair scoring",
    )
    parser.add_argument(
        "--cross-encoder-calibration",
        default=None,
        help="JSON calibration file with cross-encoder score and margin thresholds",
    )
    parser.add_argument(
        "--cross-encoder-score-threshold",
        type=float,
        default=None,
        help="raw cross-encoder score threshold for calibrated selective acceptance",
    )
    parser.add_argument(
        "--cross-encoder-margin-threshold",
        type=float,
        default=None,
        help="top-1 minus top-2 score margin threshold for calibrated acceptance",
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


def _run_dashboard(args: argparse.Namespace) -> None:
    write_dashboard(args.runs, args.output)
    print(f"Wrote dashboard to {args.output}")


def _run_agent_loop(args: argparse.Namespace) -> None:
    summary = run_agent_loop(
        routes_path=args.routes,
        tasks_path=args.tasks,
        skills_index_path=args.skills_index,
        output_dir=args.output_dir,
        condition=args.condition,
        run_label=args.run_label,
    )
    print(
        "Wrote agent loop traces to "
        f"{args.output_dir}: {summary['agent_success_count']}/"
        f"{summary['task_count']} succeeded"
    )


def _run_judge_agent_loop(args: argparse.Namespace) -> None:
    summary = judge_agent_loop(
        traces_path=args.traces,
        output_dir=args.output_dir,
        run_label=args.run_label,
        backend=args.backend,
    )
    print(
        "Wrote agent-loop judge artifacts to "
        f"{args.output_dir}: {summary['judge_pass_count']}/"
        f"{summary['task_count']} passed"
    )


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


def _run_improve_skills(args: argparse.Namespace) -> None:
    result_path = Path(args.runs) / args.router / "results.jsonl"
    if not result_path.exists():
        raise ValueError(f"router results do not exist: {result_path}")

    records = _read_jsonl_records(result_path)
    skills = load_skill_index(args.index)
    tasks = load_tasks(args.tasks)
    patches = propose_skill_patches(records, skills, tasks)
    write_patches_json(patches, args.output)

    if args.patched_index:
        save_skill_index(apply_skill_patches(skills, patches), args.patched_index)
    if args.report:
        write_patch_report(patches, args.report)

    print(f"Wrote {len(patches)} skill patch proposals to {args.output}")


def _run_judge_improvement(args: argparse.Namespace) -> None:
    baseline_records = _read_router_records(args.runs, args.baseline)
    candidate_records = _read_router_records(args.runs, args.candidate)
    status = write_acceptance_report(
        baseline_records,
        candidate_records,
        args.output,
        baseline_name=args.baseline,
        candidate_name=args.candidate,
    )
    print(f"Wrote improvement acceptance report to {args.output}: {status}")


def _run_rank_skill_patches(args: argparse.Namespace) -> None:
    summary = rank_skill_patches(
        judge_results_path=args.judge_results,
        routes_path=args.routes,
        tasks_path=args.tasks,
        skills_index_path=args.skills_index,
        output_dir=args.output_dir,
    )
    print(
        "Wrote skill patch ranking artifacts to "
        f"{args.output_dir}: {summary['candidate_count']} candidates"
    )


def _run_simulate_skill_patches(args: argparse.Namespace) -> None:
    skills = load_skill_index(args.skills_index)
    tasks = load_tasks(args.tasks)
    router = _router(args.router, args)
    router_label = (
        f"{_default_router_label(args.router, getattr(args, 'embedding_backend', None))}"
        "-shadow"
    )
    summary = simulate_skill_patches(
        ranked_patches=read_ranked_patches(args.ranked_patches),
        baseline_records_path=args.baseline_routes,
        tasks=tasks,
        skills=skills,
        router=router,
        router_label=router_label,
        top_k=args.top_k,
        max_patches=args.max_patches,
        output_dir=args.output_dir,
        input_paths={
            "ranked_patches": args.ranked_patches,
            "baseline_routes": args.baseline_routes,
            "tasks": args.tasks,
            "skills_index": args.skills_index,
        },
    )
    print(
        "Wrote patch simulation artifacts to "
        f"{args.output_dir}: {summary['guard_status']}"
    )


def _run_export_embedding_training_data(args: argparse.Namespace) -> None:
    tasks = load_tasks(args.tasks)
    skills = load_skill_index(args.skills_index)
    pairs, summary = export_embedding_training_pairs(
        tasks=tasks,
        skills=skills,
        input_paths={"tasks": args.tasks, "skills_index": args.skills_index},
    )
    output_dir = ensure_dir(args.output_dir)
    write_training_pairs(
        pairs,
        summary,
        pairs_path=output_dir / "training-pairs.jsonl",
        summary_path=output_dir / "training-summary.json",
    )
    print(f"Wrote {summary['pair_count']} embedding training pairs to {output_dir}")


def _run_judge_finetuned_embedding(args: argparse.Namespace) -> None:
    summary = write_finetuned_eval_summary(
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        output_dir=args.output_dir,
        baseline_router=args.baseline_router,
        candidate_router=args.candidate_router,
        model_dir=args.model_dir,
        apply_split=args.apply_split,
        write_filtered_results=args.write_filtered_results,
    )
    print(
        "Wrote fine-tuned embedding evaluation to "
        f"{args.output_dir}: {summary['guard_status']}"
    )


def _run_write_blind_validation(args: argparse.Namespace) -> None:
    summary = write_blind_validation_summary(
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        output_dir=args.output_dir,
        baseline_router=args.baseline_router,
        candidate_router=args.candidate_router,
        model_dir=args.model_dir,
        task_root=args.task_root,
    )
    print(
        "Wrote Phase 16 blind validation summary to "
        f"{args.output_dir}: guard={summary['guard_status']}, "
        f"tasks={summary['task_count']}"
    )


def _run_verify_release(args: argparse.Namespace) -> None:
    summary = write_release_check_summary(
        public_roots=[Path(path) for path in args.public_root],
        required_paths=[Path(path) for path in args.required_path],
        output_path=Path(args.summary_output),
    )
    print(f"Release check {summary['status']}: {args.summary_output}")
    if summary["status"] != "PASS":
        raise ValueError(f"release check status: {summary['status']}")


def _run_select_release_router(args: argparse.Namespace) -> None:
    policy = {
        "max_regressions": args.max_regressions,
        "max_negative_hit_delta": args.max_negative_hit_delta,
        "max_negative_accepted_delta": args.max_negative_accepted_delta,
        "min_recall_at_5_delta": args.min_recall_at_5_delta,
        "min_mrr_delta": args.min_mrr_delta,
        "min_ndcg_at_5_delta": args.min_ndcg_at_5_delta,
    }
    decision = write_release_decision(
        regression_summary_path=Path(args.regression_summary),
        route_diffs_path=Path(args.route_diffs),
        output_dir=Path(args.output_dir),
        policy=policy,
    )
    print(
        "Wrote Phase 17 release decision to "
        f"{args.output_dir}: {decision['decision']}"
    )


def _run_release_check(args: argparse.Namespace) -> None:
    phase17_output = Path(args.phase17_output_dir)
    release_output = ensure_dir(args.release_output_dir)
    release_summary_path = release_output / "release-check-summary.json"

    write_release_decision(
        regression_summary_path=Path(args.regression_summary),
        route_diffs_path=Path(args.route_diffs),
        output_dir=phase17_output,
    )

    manifest_json = release_output / "release-manifest.json"
    _write_placeholder_release_manifest(
        decision_path=phase17_output / "release-decision.json",
        release_check_summary_path=release_summary_path,
        output_dir=release_output,
    )
    public_roots = _unique_paths(
        [Path(path) for path in (args.public_root or DEFAULT_RELEASE_ROOTS)]
        + [release_output]
    )
    required_paths = _unique_paths(
        [Path(path) for path in (args.required_path or DEFAULT_RELEASE_REQUIRED_PATHS)]
        + [manifest_json, release_output / "release-manifest.md"]
    )
    summary = write_release_check_summary(
        public_roots=public_roots,
        required_paths=required_paths,
        output_path=release_summary_path,
    )

    verify_argv = _verify_release_argv(
        public_roots=public_roots,
        required_paths=required_paths,
        release_summary_path=release_summary_path,
    )

    command_records = [
        {
            "name": "select-release-router",
            "argv": [
                "skilleval",
                "select-release-router",
                "--regression-summary",
                args.regression_summary,
                "--route-diffs",
                args.route_diffs,
                "--output-dir",
                str(phase17_output),
            ],
            "outputs": [
                str(phase17_output / "release-decision.json"),
                str(phase17_output / "release-decision.md"),
                str(phase17_output / "task-decisions.jsonl"),
            ],
        },
        {
            "name": "verify-release",
            "argv": verify_argv,
            "outputs": [str(release_summary_path)],
        },
    ]
    artifact_paths = [
        Path(args.regression_summary),
        Path(args.route_diffs),
        phase17_output / "release-decision.json",
        phase17_output / "release-decision.md",
        phase17_output / "task-decisions.jsonl",
        release_summary_path,
    ]
    manifest, summary = _write_stable_release_manifest(
        decision_path=phase17_output / "release-decision.json",
        release_check_summary_path=release_summary_path,
        artifact_paths=artifact_paths,
        command_records=command_records,
        output_dir=release_output,
        public_roots=public_roots,
        required_paths=required_paths,
        initial_summary=summary,
    )

    if summary["status"] != "PASS":
        raise ValueError(f"release check status: {summary['status']}")
    if manifest["status"] != "PASS":
        raise ValueError(f"release manifest status: {manifest['status']}")

    print(f"Release reproducibility {manifest['status']}: {manifest_json}")


def _verify_release_argv(
    *,
    public_roots: list[Path],
    required_paths: list[Path],
    release_summary_path: Path,
) -> list[str]:
    argv = ["skilleval", "verify-release"]
    for path in public_roots:
        argv.extend(["--public-root", str(path)])
    for path in required_paths:
        argv.extend(["--required-path", str(path)])
    argv.extend(["--summary-output", str(release_summary_path)])
    return argv


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _write_stable_release_manifest(
    *,
    decision_path: Path,
    release_check_summary_path: Path,
    artifact_paths: list[Path],
    command_records: list[dict[str, object]],
    output_dir: Path,
    public_roots: list[Path],
    required_paths: list[Path],
    initial_summary: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    summary = initial_summary
    for _ in range(3):
        manifest = write_release_manifest(
            decision_path=decision_path,
            release_check_summary_path=release_check_summary_path,
            artifact_paths=artifact_paths,
            command_records=command_records,
            output_dir=output_dir,
        )
        next_summary = write_release_check_summary(
            public_roots=public_roots,
            required_paths=required_paths,
            output_path=release_check_summary_path,
        )
        if next_summary == summary:
            return manifest, next_summary
        summary = next_summary
    raise ValueError("release check summary did not stabilize")


def _write_placeholder_release_manifest(
    *,
    decision_path: Path,
    release_check_summary_path: Path,
    output_dir: Path,
) -> None:
    placeholder_summary = {
        "status": "PASS",
        "match_count": 0,
        "checks": [],
        "matches": {"sensitive": [], "overclaims": [], "checkpoints": []},
    }
    release_check_summary_path.parent.mkdir(parents=True, exist_ok=True)
    if not release_check_summary_path.exists():
        release_check_summary_path.write_text(
            json.dumps(placeholder_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    write_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_check_summary_path,
        artifact_paths=[decision_path, release_check_summary_path],
        command_records=[],
        output_dir=output_dir,
    )


def _run_write_model_manifest(args: argparse.Namespace) -> None:
    write_model_manifest(
        model_dir=args.local_model_dir or args.model_dir,
        model_dir_label=args.model_dir,
        output_path=args.output,
    )


def _run_write_finetuned_provenance(args: argparse.Namespace) -> None:
    write_finetuned_provenance_pack(
        training_summary_path=args.training_summary,
        train_config_path=args.train_config,
        train_run_summary_path=args.train_run_summary,
        model_manifest_path=args.model_manifest,
        regression_summary_path=args.regression_summary,
        output_dir=args.output_dir,
    )


def _run_calibrate_cross_encoder(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    records = _read_jsonl_records(Path(args.results))
    calibration = fit_cross_encoder_calibration(
        records,
        fit_split=args.fit_split,
        max_negative_hit_rate=args.max_negative_hit_rate,
        max_selection_rate_at_5=args.max_selection_rate_at_5,
        top_k=args.top_k,
    )
    write_cross_encoder_calibration(calibration, args.output)

    if args.calibrated_output:
        output_records = [
            apply_cross_encoder_calibration(
                record,
                calibration,
                top_k=args.top_k,
                router=args.router_label,
            )
            for record in records
            if args.apply_split == "all" or record.get("split", "dev") == args.apply_split
        ]
        if not output_records:
            raise ValueError(f"no records matched apply split: {args.apply_split}")
        output = Path(args.calibrated_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "".join(
                json.dumps(record, sort_keys=True) + "\n"
                for record in output_records
            ),
            encoding="utf-8",
        )

    print(
        "Wrote cross-encoder calibration to "
        f"{args.output}: score>={calibration.score_threshold:.6g}, "
        f"margin>={calibration.margin_threshold:.6g}"
    )


def _router(name: str, args: argparse.Namespace | None = None) -> SkillRouter:
    if name == "keyword":
        return KeywordRouter()
    if name == "hybrid":
        return HybridRouter()
    if name == "embedding":
        return _embedding_router(args)
    if name == "gated":
        return _gated_router(args)
    if name == "cross-encoder":
        return _cross_encoder_router(args)
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
        selective=getattr(args, "selective", False),
        min_confidence=getattr(args, "min_confidence", 0.5),
        contrastive_selective=getattr(args, "contrastive_selective", False),
        contrastive_margin=getattr(args, "contrastive_margin", 6.0),
        min_evidence=getattr(args, "min_evidence", 2.0),
    )


def _cross_encoder_router(args: argparse.Namespace | None) -> CrossEncoderReranker:
    model_name = getattr(
        args,
        "cross_encoder_model",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    batch_size = getattr(args, "cross_encoder_batch_size", 16)
    score_threshold, margin_threshold = _cross_encoder_thresholds(args)
    return CrossEncoderReranker(
        base_router=_embedding_router(args),
        model=SentenceTransformerCrossEncoderModel(model_name, batch_size=batch_size),
        candidate_pool_size=getattr(args, "gated_pool_size", 10),
        selective=getattr(args, "selective", False) or score_threshold is not None,
        min_confidence=getattr(args, "min_confidence", 0.5),
        contrastive_selective=getattr(args, "contrastive_selective", False),
        contrastive_margin=getattr(args, "contrastive_margin", 6.0),
        min_evidence=getattr(args, "min_evidence", 2.0),
        raw_score_threshold=score_threshold,
        margin_threshold=margin_threshold,
        cross_encoder_batch_size=batch_size,
    )


def _cross_encoder_thresholds(args: argparse.Namespace | None) -> tuple[float | None, float]:
    calibration_path = getattr(args, "cross_encoder_calibration", None)
    calibration = (
        read_cross_encoder_calibration(calibration_path)
        if calibration_path
        else None
    )
    score_threshold = getattr(args, "cross_encoder_score_threshold", None)
    margin_threshold = getattr(args, "cross_encoder_margin_threshold", None)
    if calibration is not None:
        if score_threshold is None:
            score_threshold = calibration.score_threshold
        if margin_threshold is None:
            margin_threshold = calibration.margin_threshold
    return score_threshold, 0.0 if margin_threshold is None else margin_threshold


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

    router_name, _, raw_embedding_backend = target.partition(":")
    router_name = router_name.strip()
    embedding_backend = raw_embedding_backend.strip() or None
    if router_name not in ROUTER_NAMES:
        raise ValueError(f"unknown router(s): {router_name}")
    if embedding_backend is not None:
        if router_name in ("embedding", "gated"):
            if embedding_backend not in EMBEDDING_BACKENDS:
                raise ValueError(f"unknown embedding backend: {embedding_backend}")
        elif router_name == "cross-encoder":
            if embedding_backend not in RERANKER_BACKENDS:
                raise ValueError(f"unknown cross-encoder backend: {embedding_backend}")
        else:
            raise ValueError(
                "only embedding, gated, or cross-encoder router specs can "
                "include a backend"
            )

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


def _read_jsonl_records(path: Path) -> list[dict[str, object]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"no result records found in {path}")
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"expected object in {path} at line {index}")
    return records


def _read_router_records(runs_dir: Path | str, router: str) -> list[dict[str, object]]:
    result_path = Path(runs_dir) / router / "results.jsonl"
    if not result_path.exists():
        raise ValueError(f"router results do not exist: {result_path}")
    return _read_jsonl_records(result_path)


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
        "split": task.split,
        "robustness_tags": task.robustness_tags,
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
        "accepted_count": accepted_count(selected),
        "coverage": coverage(selected),
        "selection_rate_at_5": selection_rate_at_k(selected, 5),
        "abstention_rate": abstention_rate(selected),
        "accepted_recall_at_5": accepted_recall_at_k(selected, gold, 5),
        "negative_accepted_rate": negative_accepted_rate(selected, negative, 5),
    }


if __name__ == "__main__":
    raise SystemExit(main())
