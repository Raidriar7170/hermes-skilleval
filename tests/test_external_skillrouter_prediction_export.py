import gzip
import json
import shutil
from pathlib import Path

import pytest

from hermes_skilleval.cli import main
from hermes_skilleval.external.skillrouter_scorer import score_skillrouter_predictions
from hermes_skilleval.external.skillrouter_prediction_export import (
    FrozenRouterConfig,
    write_skillrouter_prediction_artifacts,
    write_skillrouter_prediction_file,
)
from hermes_skilleval.routers.embedding import HashingEmbeddingModel
from hermes_skilleval.release_manifest import sha256_file


FIXTURE = Path(__file__).parent / "fixtures" / "external" / "skillrouter_eval_core_tiny"


def test_exported_predictions_are_accepted_by_existing_scorer_and_manifested(tmp_path):
    manifest = write_skillrouter_prediction_artifacts(
        data_root=FIXTURE,
        output_dir=tmp_path / "predictions",
        run_id="fixture-export",
        configs=[
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__metadata__easy",
                field_view="metadata",
                tier="easy",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            )
        ],
        top_k=50,
        command=["skilleval", "external-export-predictions", "--fixture"],
        embedding_model=HashingEmbeddingModel(dimensions=64),
    )

    artifact = manifest["artifacts"][0]
    predictions_path = Path(artifact["output_path"])
    predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
    assert set(predictions) == {
        "task-single-easy",
        "task-multi-hard",
        "task-generic-easy",
        "task-medium-easy-pool",
    }
    assert artifact["sha256"] == sha256_file(predictions_path)
    assert artifact["size_bytes"] == predictions_path.stat().st_size
    assert manifest["relevance_labels_read"] is False
    assert manifest["top_k"] == 50
    assert manifest["code"]["commit"]
    assert manifest["command"] == ["skilleval", "external-export-predictions", "--fixture"]

    report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=predictions_path,
        tier="easy",
        mode="core",
    )
    assert report["aggregates"]["all"]["task_count"] == 2


def test_exporter_filters_predictions_to_selected_candidate_tier(tmp_path):
    manifest = write_skillrouter_prediction_artifacts(
        data_root=FIXTURE,
        output_dir=tmp_path / "predictions",
        run_id="tier-export",
        configs=[
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__full_body__easy",
                field_view="full_body",
                tier="easy",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            ),
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__full_body__hard",
                field_view="full_body",
                tier="hard",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            ),
        ],
        top_k=50,
        command=["fixture"],
        embedding_model=HashingEmbeddingModel(dimensions=64),
    )

    by_config = {artifact["config_id"]: artifact for artifact in manifest["artifacts"]}
    easy_predictions = json.loads(
        Path(by_config["baseline-minilm__full_body__easy"]["output_path"]).read_text(
            encoding="utf-8"
        )
    )
    hard_predictions = json.loads(
        Path(by_config["baseline-minilm__full_body__hard"]["output_path"]).read_text(
            encoding="utf-8"
        )
    )
    easy_ids = {skill_id for ranking in easy_predictions.values() for skill_id in ranking}
    hard_ids = {skill_id for ranking in hard_predictions.values() for skill_id in ranking}
    assert easy_ids == {
        "gt/browser-login",
        "degraded/browser-login",
        "gt/medium-easy",
    }
    assert hard_ids == {
        "gt/workflow-debugging",
        "gt/tdd-helper",
        "degraded/workflow-debugging",
    }


def test_exporter_is_deterministic_and_deduplicates_rankings(tmp_path):
    root = _fixture_with_duplicate_easy_skill(tmp_path)
    kwargs = {
        "data_root": root,
        "run_id": "dedupe-export",
        "configs": [
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__name_only__easy",
                field_view="name_only",
                tier="easy",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            )
        ],
        "top_k": 50,
        "command": ["fixture"],
        "embedding_model": HashingEmbeddingModel(dimensions=64),
    }

    first = write_skillrouter_prediction_artifacts(
        output_dir=tmp_path / "first",
        **kwargs,
    )
    second = write_skillrouter_prediction_artifacts(
        output_dir=tmp_path / "second",
        **kwargs,
    )

    first_predictions = json.loads(
        Path(first["artifacts"][0]["output_path"]).read_text(encoding="utf-8")
    )
    second_predictions = json.loads(
        Path(second["artifacts"][0]["output_path"]).read_text(encoding="utf-8")
    )
    assert first_predictions == second_predictions
    for ranking in first_predictions.values():
        assert len(ranking) == len(set(ranking))


def test_prediction_file_writer_fails_closed_on_unknown_skill_id(tmp_path):
    with pytest.raises(ValueError, match="unknown predicted skill id"):
        write_skillrouter_prediction_file(
            output_path=tmp_path / "predictions.json",
            predictions={"task-1": ["missing-skill"]},
            task_ids={"task-1"},
            tier_skill_ids={"known-skill"},
        )


def test_exporter_enforces_top_k_and_minimum_official_depth(tmp_path):
    root = _fixture_with_many_easy_skills(tmp_path, count=55)
    config = FrozenRouterConfig(
        router_id="baseline-minilm",
        config_id="baseline-minilm__metadata__easy",
        field_view="metadata",
        tier="easy",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="fixture-revision",
    )

    with pytest.raises(ValueError, match="top_k must be at least 50"):
        write_skillrouter_prediction_artifacts(
            data_root=root,
            output_dir=tmp_path / "too-shallow",
            run_id="bad-top-k",
            configs=[config],
            top_k=49,
            command=["fixture"],
            embedding_model=HashingEmbeddingModel(dimensions=64),
        )

    manifest = write_skillrouter_prediction_artifacts(
        data_root=root,
        output_dir=tmp_path / "predictions",
        run_id="top-k-export",
        configs=[config],
        top_k=50,
        command=["fixture"],
        embedding_model=HashingEmbeddingModel(dimensions=64),
    )
    predictions = json.loads(
        Path(manifest["artifacts"][0]["output_path"]).read_text(encoding="utf-8")
    )
    assert all(len(ranking) == 50 for ranking in predictions.values())


def test_exporter_manifest_includes_hash_and_size_for_every_prediction_file(tmp_path):
    manifest = write_skillrouter_prediction_artifacts(
        data_root=FIXTURE,
        output_dir=tmp_path / "predictions",
        run_id="manifest-export",
        configs=[
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__metadata__easy",
                field_view="metadata",
                tier="easy",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            ),
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__metadata__hard",
                field_view="metadata",
                tier="hard",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            ),
        ],
        top_k=50,
        command=["fixture"],
        embedding_model=HashingEmbeddingModel(dimensions=64),
    )

    assert len(manifest["artifacts"]) == 2
    for artifact in manifest["artifacts"]:
        output_path = Path(artifact["output_path"])
        assert artifact["status"] == "PASS"
        assert artifact["sha256"] == sha256_file(output_path)
        assert artifact["size_bytes"] == output_path.stat().st_size
        assert artifact["candidate_pool"]["sha256"]
        assert artifact["candidate_pool"]["size_bytes"] > 0


def test_exporter_fails_closed_on_duplicate_config_id(tmp_path):
    config = FrozenRouterConfig(
        router_id="baseline-minilm",
        config_id="duplicated",
        field_view="metadata",
        tier="easy",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="fixture-revision",
    )

    with pytest.raises(ValueError, match="duplicate config_id"):
        write_skillrouter_prediction_artifacts(
            data_root=FIXTURE,
            output_dir=tmp_path / "predictions",
            run_id="duplicate-export",
            configs=[config, config],
            top_k=50,
            command=["fixture"],
            embedding_model=HashingEmbeddingModel(dimensions=64),
        )


def test_exporter_does_not_require_relevance_json_for_prediction_generation(tmp_path):
    root = tmp_path / "without-relevance"
    shutil.copytree(FIXTURE, root)
    (root / "relevance.json").unlink()

    manifest = write_skillrouter_prediction_artifacts(
        data_root=root,
        output_dir=tmp_path / "predictions",
        run_id="no-relevance-export",
        configs=[
            FrozenRouterConfig(
                router_id="baseline-minilm",
                config_id="baseline-minilm__name_only__easy",
                field_view="name_only",
                tier="easy",
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_revision="fixture-revision",
            )
        ],
        top_k=50,
        command=["fixture"],
        embedding_model=HashingEmbeddingModel(dimensions=64),
    )

    assert manifest["relevance_labels_read"] is False
    assert Path(manifest["artifacts"][0]["output_path"]).exists()


def test_cli_external_export_predictions_writes_manifest_and_unavailable_entries(tmp_path):
    output_dir = tmp_path / "cli-predictions"

    exit_code = main(
        [
            "external-export-predictions",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(FIXTURE),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "cli-export",
            "--embedding-backend",
            "hashing",
            "--baseline-minilm-revision",
            "fixture-revision",
            "--router-config",
            "baseline-minilm:metadata:easy",
            "--router-config",
            "finetuned-embedding:metadata:easy",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    by_config = {artifact["config_id"]: artifact for artifact in manifest["artifacts"]}
    assert by_config["baseline-minilm__metadata__easy"]["status"] == "PASS"
    assert Path(by_config["baseline-minilm__metadata__easy"]["output_path"]).exists()
    assert by_config["finetuned-embedding__metadata__easy"]["status"] == "UNAVAILABLE"
    assert "checkpoint_path is not configured" in by_config[
        "finetuned-embedding__metadata__easy"
    ]["reason"]


def _fixture_with_duplicate_easy_skill(tmp_path: Path) -> Path:
    root = tmp_path / "duplicate-skill"
    shutil.copytree(FIXTURE, root)
    shard = root / "easy" / "shard-000.jsonl.gz"
    rows = gzip.open(shard, "rt", encoding="utf-8").read().splitlines()
    rows.append(rows[0])
    with gzip.open(shard, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(rows) + "\n")
    return root


def _fixture_with_many_easy_skills(tmp_path: Path, *, count: int) -> Path:
    root = tmp_path / "many-skills"
    shutil.copytree(FIXTURE, root)
    shard = root / "easy" / "shard-000.jsonl.gz"
    rows = [
        {
            "id": f"fixture/skill-{index:03d}",
            "name": f"Fixture Skill {index:03d}",
            "description": f"Fixture skill number {index:03d}",
            "body": f"Use fixture skill {index:03d} for deterministic routing.",
            "tier": "easy",
        }
        for index in range(count)
    ]
    with gzip.open(shard, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return root
