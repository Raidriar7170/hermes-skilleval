# Reproducible entry points

All commands run from the ASI worktree with an isolated Python environment. No global Codex configuration is changed. Use `python -m hermes_skilleval.intervention.cli` before package installation; `pip install -e '.[intervention-train]'` in a separate virtual environment installs the equivalent `hermes-intervention` entry point. The training extra is optional; ordinary Hermes commands and records-only replay do not load model weights.

Set task-specific paths, not `HOME` or `CODEX_HOME`:

```sh
ASI_PRIVATE=/path/to/private/asi
ASI_ENCODER=/path/to/pinned/all-MiniLM-L6-v2/snapshot
ASI_TASKS="$ASI_PRIVATE/tasks-candidate-v4"
ASI_PROTOCOL="$ASI_PRIVATE/protocol-v2.json"
ASI_SKILLS=configs/conditional-applicability-v1/skills
ASI_PAYLOADS=configs/adaptive-skill-intervention-v1/payloads
```

The private task directory contains each original base, qualification-only reference, public `request.txt`, `task.json` and controller-owned `trusted` checks. Existing source snapshots can be materialized with `scripts/intervention/prepare_tasks.py`; `finalize_task_assets.py` constructs independent qualification references and refined developer checks. `qualify_tasks.py` and `qualification_controls.py` test base/reference/negative controls before `freeze_study.py` writes an immutable protocol. Their `--help` flags enumerate source and output roots. These steps call no Agent. Preserve every qualification attempt and do not run finalization twice on the same reference directory.

Build the isolated derivative image from the existing executor:

```sh
docker build -f configs/adaptive-skill-intervention-v1/Executor.Dockerfile -t hermes-asi-executor:v1 .
```

The protocol binds the actual image ID, pretrained encoder files, full original skill directory and registry, bounded payloads, requests, source snapshots and checks. A changed image or asset fails preparation; a tag alone is not sufficient identity.

```sh
python -m hermes_skilleval.intervention.cli prepare \
  --protocol "$ASI_PROTOCOL" --tasks "$ASI_TASKS" \
  --skills "$ASI_SKILLS" --payloads "$ASI_PAYLOADS" --encoder "$ASI_ENCODER"

python -m hermes_skilleval.intervention.cli collect \
  --protocol "$ASI_PROTOCOL" --tasks "$ASI_TASKS" --output "$ASI_PRIVATE/collection-v1" \
  --skills "$ASI_SKILLS" --payloads "$ASI_PAYLOADS" --encoder "$ASI_ENCODER"

python -m hermes_skilleval.intervention.cli train \
  --records "$ASI_PRIVATE/collection-v1/records.json" --output "$ASI_PRIVATE/models-v1" \
  --payloads "$ASI_PAYLOADS" --encoder "$ASI_ENCODER"

# A separate process must reproduce the saved probes before final evaluation.
python -m hermes_skilleval.intervention.cli reload --models "$ASI_PRIVATE/models-v1"

python scripts/intervention/diagnose_development.py \
  --records "$ASI_PRIVATE/collection-v1/records.json" --models "$ASI_PRIVATE/models-v1" \
  --payloads "$ASI_PAYLOADS" --encoder "$ASI_ENCODER" \
  --output "$ASI_PRIVATE/development-diagnostics.json"

python -m hermes_skilleval.intervention.cli evaluate \
  --protocol "$ASI_PROTOCOL" --tasks "$ASI_TASKS" --output "$ASI_PRIVATE/evaluation-v1" \
  --skills "$ASI_SKILLS" --payloads "$ASI_PAYLOADS" --encoder "$ASI_ENCODER" \
  --models "$ASI_PRIVATE/models-v1"

python -m hermes_skilleval.intervention.cli replay --records "$ASI_PRIVATE/collection-v1/records.json"
python -m hermes_skilleval.intervention.cli replay --records "$ASI_PRIVATE/evaluation-v1/records.json"
```

`collect` and `evaluate` use the existing local Codex account inside an ephemeral controller-owned session home. Only the authentication file is copied, with restrictive permissions, and it is removed in `finally`; do not commit this directory. The Agent's tool permissions deny access to that home. An existing completed execution is reused by identity. An interrupted reserved sample remains unknown; rerunning a command does not silently draw a replacement sample. Training refuses to overwrite an existing model directory.

`replay` is records-only: no Docker, Agent, network, model loading or training. It independently checks the retained patch digest, candidate/snapshot/reconstruction equality, verifier artifact digests, collected-test identities and JUnit outcomes before recomputing quality and utility. It requires the retained private evidence directory; the compact public report alone cannot prove a fresh behavioral run.

The final table must include all 96 scheduled runs, including unknowns. Interpret success over scheduled runs alongside valid-run counts; do not delete unknowns to improve percentages. Bootstrap resamples tasks, not states or repetitions. The final evaluation freezes saved model identities before its first test call and refuses changed models on continuation.


After private replay passes, `scripts/intervention/export_study.py` exports all captured patches, fixed checks, verifier XML, compact rows, model identities and training diagnostics. The export contains neither full source datasets nor model weights or raw Agent history. `hermes-intervention replay --records artifacts/adaptive-skill-intervention-v1/evaluation-records.json` verifies this portable record package without loading a model. This proves consistency with captured verifier outputs; rerunning source behavior still requires the original public bases and isolated checker.

`continue_study.py` can wait for the existing collector process, then run private replay, actual training, independent reload, the predetermined development diagnostics, all final comparisons and final replay in sequence. It has no outcome-based retry or model selection loop. Any engineering exception stops the chain with a diagnostic status and leaves all attempts intact.
