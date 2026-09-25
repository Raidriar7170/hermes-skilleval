"""Export compact, public-only records from local Phase 1 evidence."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_gap_phase1 import public_only

ROOT = Path(__file__).resolve().parents[2]
P = Path(os.environ.get("NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"))
OUT = ROOT / "artifacts/native-gap-phase1-v1"


def compact(value):
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, dict):
        result = {k: compact(v) for k, v in value.items()}
        output = result.get("aggregatedOutput")
        if isinstance(output, str) and len(output) > 2500:
            result["aggregatedOutput_sha256"] = hashlib.sha256(
                output.encode()
            ).hexdigest()
            result["aggregatedOutput_original_characters"] = len(output)
            result["aggregatedOutput"] = (
                output[:1800] + "\n[public excerpt truncated]\n" + output[-700:]
            )
        return result
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(compact(public_only(value)), indent=2, ensure_ascii=False)
    text = text.replace(str(P), "$PRIVATE").replace("/private" + str(P), "$PRIVATE")
    path.write_text(text + "\n")


def usage(events):
    found = [
        e["params"].get("tokenUsage")
        for e in events
        if e.get("method") == "thread/tokenUsage/updated"
    ]
    return found[-1] if found else None


for version in ["v1", "v2"]:
    for f in sorted((P / ("probe-results-" + version)).glob("*/result.json")):
        d = json.loads(f.read_text())
        d.pop("models", None)
        commands = [
            e["params"]["item"].get("command", "")
            for e in d["public_events"]
            if e.get("method") == "item/completed"
            and e["params"]["item"].get("type") == "commandExecution"
        ]
        final = [
            e["params"]["item"].get("text", "")
            for e in d["public_events"]
            if e.get("method") == "item/completed"
            and e["params"]["item"].get("type") == "agentMessage"
        ]
        d["observations"] = {
            "discovered": all(
                any(s["name"] == n for s in d["skills"]["data"][0]["skills"])
                for n in [
                    "table-field-inventory",
                    "python-test-entry",
                    "package-notes-check",
                ]
            ),
            "body_read_observed": any("SKILL.md" in c for c in commands),
            "body_marker_observed": any(
                marker in "\n".join(final)
                for marker in ["FIELD_LEDGER_V1", "TEST_ENTRY_V1", "PACKAGE_NOTES_V1"]
            ),
            "action_observed": bool(commands),
            "task_completed": version == "v2",
            "task_completion_oracle": "CSV two rows/name-city/one empty city; pytest testpaths tests without execution; arithmetic 437; manually checked final text and public commands"
            if version == "v2"
            else "MODEL_REQUEST_REJECTED",
            "progressive_loading_observable": "PARTIAL_INITIAL_CONTEXT_NOT_EXPOSED",
        }
        d["usage"] = usage(d["public_events"])
        save(OUT / "probes" / version / f.parent.name / "result.json", d)

for name in ["sandbox-preflight-v1", "sandbox-preflight-v2", "sandbox-preflight-v3"]:
    d = json.loads((P / name / "result.json").read_text())
    d.pop("task", None)
    d.pop("public_events", None)
    save(OUT / "preflight" / (name + ".json"), d)

r = json.loads((P / "memory-seed1/result.json").read_text())
db = sqlite3.connect(
    "file:" + str(P / "memory-seed1/state/state_5.sqlite") + "?mode=ro", uri=True
)
row = db.execute(
    "select id,source,memory_mode,cli_version,model,reasoning_effort,updated_at from threads"
).fetchone()
db.close()
memory = {
    "configuration": "ENABLED_VERIFIED",
    "generation": "PENDING_NATIVE_ELIGIBILITY",
    "use": "NOT_RUN",
    "seed_sessions": 1,
    "seed_terminal": r["terminal"],
    "seed_seconds": r["elapsed_seconds"],
    "seed_usage": usage(r["public_events"]),
    "persisted_thread": dict(
        zip(
            [
                "id",
                "source",
                "memory_mode",
                "cli_version",
                "model",
                "reasoning_effort",
                "updated_at",
            ],
            row,
        )
    ),
    "effective_explicit_settings": r["config"]["config"]["memories"],
    "feature_flag": r["config"]["config"]["features"]["memories"],
    "default_idle_hours": 6,
    "default_min_rate_limit_remaining_percent": 25,
    "eligibility_reference": "https://github.com/openai/codex/blob/rust-v0.155.0-alpha.16.4/codex-rs/config/src/types.rs",
    "eligible_source_reference": "https://github.com/openai/codex/blob/rust-v0.155.0-alpha.16.4/codex-rs/rollout/src/lib.rs",
    "raw_memories_status": "Native scaffold says No raw memories yet; no generated case summaries",
    "generated_summary_files": len(
        list((P / "memory-seed1/state/memories/rollout_summaries").glob("*"))
    ),
    "active_additional_wait_seconds": 0,
    "wait_reason": "6 hour default exceeds allowed 20 minute active window; observed while continuing independent work",
    "generation_calls_observed": 0,
    "generation_calls_caveat": "No generated summaries or corresponding public usage observed; no provider billing audit",
    "background_process_retained": False,
}
save(OUT / "memory.json", memory)

images = []
for name in [
    "swerebench/sweb.eval.x86_64.asottile_1776_pyupgrade-330",
    "swerebench/sweb.eval.x86_64.encode_1776_httpx-386",
    "hermes-native-gap-httpx386:v1",
]:
    d = json.loads(subprocess.check_output(["docker", "image", "inspect", name]))[0]
    images.append(
        {
            "reference": name,
            "id": d["Id"],
            "digests": d.get("RepoDigests"),
            "architecture": d["Architecture"],
            "os": d["Os"],
            "uncompressed_image_bytes": d["Size"],
        }
    )
save(
    OUT / "runtime.json",
    {
        "client": "0.155.0-alpha.16.4",
        "model": "gpt-6-sol",
        "effort": "high",
        "authentication_type": "ChatGPT",
        "os": "macOS",
        "host_architecture": "arm64",
        "docker_host_architecture": "aarch64",
        "task_image_architecture": "amd64",
        "task_execution": "x86_64 emulation on Apple Silicon",
        "client_execution": "native aarch64 Linux binary, same version",
        "images": images,
        "client_installs": [
            json.loads((P / x).read_text())
            for x in ["codex-linux-install.json", "codex-arm64-install.json"]
        ],
        "configuration_change_history": [
            "v1 four synthetic requests: installed CLI 0.154.0 rejected gpt-6-sol with ChatGPT auth",
            "v2 same probe semantics and model using desktop 0.155.0-alpha.16.4: four completed",
            "Linux x64 same client failed seccomp preflight without model execution; Linux arm64 same version passed sandbox canaries",
        ],
        "limitations": [
            "Preconfigured repository maintenance, web and tool network disabled",
            "Six bundled system skills are listed but their bodies under /state/skills are denied by credential-state isolation; four user skills are readable",
            "No installed personal plugins, user skills or personal memories copied",
            "Native default agent features not explicitly disabled, but subtask capability was not directly probed",
            "No complete initial context visibility",
            "No warm memory baseline",
        ],
        "image_network_transfer_bytes": None,
        "image_download_seconds": None,
        "cost_limitation": "Docker pull layer reuse and total duration not instrumented; image Size is storage size, not actual downloaded bytes; cold-start total UNKNOWN",
    },
)

for ident in ["smoke-pyupgrade330", "smoke-httpx386"]:
    f = P / ident / "result.json"
    if not f.exists():
        continue
    d = json.loads(f.read_text())
    d["usage"] = usage(d.get("public_events", []))
    d["full_online_seconds"] = None
    d["timing_limitation"] = (
        "Task JSON read/projection and frozen-input hashing in caller preceded native_smoke timer; measured interval covers state/base preparation, client, tools, output, cleanup and capture, but full online cost UNKNOWN. No rerun to replace this gap."
    )
    save(OUT / "smoke" / ident / "result.json", d)
    patch = P / ident / "candidate.patch"
    if patch.exists():
        (OUT / "smoke" / ident / "candidate.patch").write_bytes(patch.read_bytes())
    save(
        OUT / "smoke" / ident / "frozen.json",
        json.loads((P / (ident + "-frozen.json")).read_text()),
    )
