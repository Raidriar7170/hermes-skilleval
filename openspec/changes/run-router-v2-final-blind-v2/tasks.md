# Router V2 Agent-only Blind-v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` for bounded implementation tasks and `executing-plans` for sequential experiment stages. Steps use checkbox (`- [ ]`) syntax for OpenSpec tracking.

**Goal:** Replace the superseded human 64/48 blind-v2 contract with a preregistered, fully Agent-generated, dual-Agent-unanimous 128/96 contract, then execute exactly one frozen Arm A/C evaluation while always retaining `KEEP_BASELINE`.

**Architecture:** Keep the existing pure metric module, dedicated runner, and narrow CLI. Repository code builds and validates sealed request/response ledgers but does not depend on the private Codex multi-Agent API; Goal mode invokes the three approved Agent configurations and writes raw evidence to an external staging root. A superseding Commit A-agent freezes code and prompts before generation, Commit B freezes the selected dataset before Arm A/C load, and the existing single-attempt runner produces the only model result.

**Tech Stack:** Python 3.11, pytest, sentence-transformers, canonical JSON/JSONL and SHA-256, OpenSpec, Git worktrees, Codex multi-Agent runtime.

---

## Execution handoff

The user preselected Goal mode. Immediately after this plan passes self-review, create one Goal covering every pending step in Tasks 1-14. Use `subagent-driven-development` for bounded code/test slices, retain the main thread as integrator, and use sequential checkpoints for Commit A-agent, Agent construction, Commit B, and the formal attempt. Do not create a second Goal at Task 10.

## Assumptions and protected boundaries

- The current branch is `agent/router-v2-blind-v2-final`; historical commit `09ba4104a147a2f740ef69283c850f40e78a0b15` remains immutable audit history.
- Current OpenSpec edits stay uncommitted until the final preregistration commit so Commit A-agent contains the approved contract.
- Implementation may use small intermediate source/test commits before Commit A-agent. No candidate generation is allowed until the final Commit A-agent SHA exists and all pre-generation checks pass.
- Raw Agent prompts, responses, run metadata, and contamination ledgers live under `/Users/raidriar/.codex/private/hermes-blind-v2/${COMMIT_A_SHA}/`, exported as `HERMES_BLIND_V2_ROOT`; only the canonical Commit B files enter Git.
- Existing explicit authorization covers implementation, Commit A-agent, Agent construction/review, Commit B, the unique formal attempt, final result commit, branch push, and one PR. It does not authorize merge, tag, release, deploy, archive, training, checkpoint mutation, or default-router promotion.
- No Human Brief is created because the original task explicitly forbids it.

## File map

- Modify `src/hermes_skilleval/router_v2_blind_v2_evaluation.py`: 128/96 metric contract, terminal states, unchanged gate, and lineage fields.
- Modify `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py`: sealed Agent requests, external-ledger validation, contamination checks, deterministic selection/freeze, Commit A/B authority, smokes, and evaluation orchestration.
- Modify `scripts/run_router_v2_blind_v2_final.py`: request/status/freeze/model-smoke/evaluate CLI only.
- Modify `tests/test_router_v2_blind_v2_evaluation.py`: pure contract, denominator, gate, statistics, failure-slice, and lineage tests.
- Modify `tests/test_router_v2_blind_v2_evaluation_runner.py`: Agent ledger, isolation, retry, contamination, freeze, Git authority, smoke-order, CLI, and single-attempt tests.
- Modify `docs/router-v2-blind-v2-protocol.md`: executable Agent-only protocol and exact prompts/schemas.
- Modify `artifacts/router-v2-blind-v2/preregistration.json`: machine-readable Agent-only freeze and regenerated canonical hash.
- Keep the four approved OpenSpec files under `openspec/changes/run-router-v2-final-blind-v2/` consistent.
- Conditionally create only `data/router-v2-blind-v2/blind-v2-tasks.jsonl`, `blind-v2-review-summary.json`, and `blind-v2-manifest.json` in Commit B.
- Conditionally create only the existing final artifact namespace after the formal attempt.

### Task 0: Preserve verified historical groundwork

- [x] 0.1 Verify PR #38, frozen model/data authority, current `origin/main`, pre-existing CI failures, and branch cleanliness before historical Commit A.
- [x] 0.2 Preserve historical commit `09ba4104…`, its human 64/48 implementation, and its old A/C smoke receipt as superseded, non-authoritative evidence.
- [x] 0.3 Confirm no human pack, Agent candidate, Commit B, or formal attempt has been read or created.

### Task 1: Convert the pure evaluation contract to 128/96

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation.py:21-28,108-236,246-478,480-866`
- Modify: `tests/test_router_v2_blind_v2_evaluation.py:14-425`

- [x] 1.1 Replace the test route fixture with the frozen 128/96 distribution and assert the new terminal vocabulary.

```python
def _route_rows(arm: str, seed: int) -> list[dict[str, Any]]:
    rows = []
    for index in range(128):
        gold_index = index // 8
        has_negative = index % 8 < 6
        rows.append(
            {
                "task_id": f"{PREFIX}_TASK_{index:03d}",
                "semantic_family_id": f"{PREFIX}_FAMILY_{index:03d}",
                "gold_skill_id": f"test-skill-{gold_index:02d}",
                "tempting_negative_skill_id": (
                    f"test-skill-{(gold_index + 1) % 16:02d}"
                    if has_negative
                    else None
                ),
                "gold_rank": 2 if arm == "A" else 1,
                "tempting_negative_rank": 5 if has_negative and arm == "A" else (
                    6 if has_negative else None
                ),
                "latency_ns": 10_000_000,
                "arm": arm,
                "seed": seed,
            }
        )
    return rows
```

- [x] 1.2 Run the focused pure-contract tests and verify RED failures mention the old 64/48 counts or old conclusion names.

Run:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q \
  tests/test_router_v2_blind_v2_evaluation.py
```

Expected: FAIL on `POSITIVE_TASK_COUNT == 128`, `TEMPTING_NEGATIVE_COUNT == 96`, per-skill `8/6/2`, and `AGENT_BLIND_V2_*` assertions.

- [x] 1.3 Update constants, route-group validation, raw-count denominators, and conclusion fields without changing `_GATE`, seeds, ranking, bootstrap, or latency logic.

```python
POSITIVE_TASK_COUNT = 128
TEMPTING_NEGATIVE_COUNT = 96
CANONICAL_SKILL_COUNT = 16
SEMANTIC_FAMILY_COUNT = 128
TASKS_PER_GOLD_SKILL = 8
NEGATIVE_LABELED_PER_GOLD_SKILL = 6
POSITIVE_ONLY_PER_GOLD_SKILL = 2

TERMINAL_STATES = {
    "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
    "AGENT_BLIND_V2_PROTOCOL_INVALID",
    "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
    "AGENT_BLIND_V2_GATES_PASSED",
    "AGENT_BLIND_V2_GATES_NOT_PASSED",
}

def terminal_posture(research_conclusion: str) -> dict[str, Any]:
    _require(research_conclusion in TERMINAL_STATES, "terminal state mismatch")
    return {
        "research_conclusion": research_conclusion,
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
    }
```

- [x] 1.4 Make `apply_preregistered_gate()` merge `terminal_posture()` and emit only `AGENT_BLIND_V2_GATES_PASSED` or `AGENT_BLIND_V2_GATES_NOT_PASSED`.

- [x] 1.5 Re-run the focused tests; expected result is all tests in `test_router_v2_blind_v2_evaluation.py` passing.

- [x] 1.6 Commit only the pure module and its test.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation.py
git commit -m "refactor(router): scale blind-v2 contract to 128 tasks"
```

### Task 2: Define sealed Agent request and response contracts

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py:37-132,148-216`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:21-107`

- [x] 2.1 Replace CSV/human constants with exact Agent staging files, model configurations, timeouts, prompts, schemas, and deterministic schedule functions.

```python
REQUIRED_AGENT_PACK_FILES = (
    "blind-v2-generation.jsonl",
    "blind-v2-review-a.jsonl",
    "blind-v2-review-b.jsonl",
    "blind-v2-contamination.jsonl",
    "agent-run-metadata.json",
)
AGENT_CONFIGS = {
    "generator": {"model": "gpt-5.6-sol", "reasoning_effort": "max", "timeout_seconds": 1800},
    "reviewer_a": {"model": "gpt-5.6-sol", "reasoning_effort": "ultra", "timeout_seconds": 900},
    "reviewer_b": {"model": "gpt-5.6-luna", "reasoning_effort": "max", "timeout_seconds": 900},
}
SELECTION_SEED = 7170

def opaque_candidate_id(round_number: int, skill_id: str, index: int, response_sha256: str) -> str:
    raw = f"{round_number}:{skill_id}:{index}:{response_sha256}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def selection_key(candidate_id: str) -> str:
    return hashlib.sha256(f"7170:{candidate_id}".encode()).hexdigest()

def review_schedule_key(role: str, candidate_id: str) -> str:
    prefix = {"reviewer_a": "review-a:7170", "reviewer_b": "review-b:7171"}[role]
    return hashlib.sha256(f"{prefix}:{candidate_id}".encode()).hexdigest()
```

- [x] 2.2 Add RED tests proving generator requests contain only skill definitions/rules/quotas and reviewer requests contain exactly `task_id`, `prompt_text`, `canonical_skills`, and `rubric`.

```python
def test_reviewer_request_is_single_candidate_and_label_blind() -> None:
    request = runner.build_reviewer_request(
        {
            "candidate_id": "opaque-001",
            "prompt_text": f"{PREFIX} REQUEST",
            "proposed_gold_skill_id": "test-skill-00",
            "proposed_negative_skill_id": "test-skill-01",
            "rationale": f"{PREFIX} HIDDEN",
        },
        _skills(),
        role="reviewer_a",
    )
    assert set(request["input"]) == {
        "task_id", "prompt_text", "canonical_skills", "rubric"
    }
    encoded = json.dumps(request)
    assert "proposed_gold_skill_id" not in encoded
    assert "proposed_negative_skill_id" not in encoded
    assert f"{PREFIX} HIDDEN" not in encoded
```

- [x] 2.3 Implement `build_generator_request()`, `build_reviewer_request()`, request SHA-256, exact field whitelists, and Agent response validators.

```python
def build_reviewer_request(
    candidate: dict[str, Any],
    canonical_skills: list[dict[str, Any]],
    *,
    role: str,
) -> dict[str, Any]:
    _require(role in {"reviewer_a", "reviewer_b"}, "reviewer role mismatch")
    payload = {
        "schema_version": "router-v2-blind-v2-review-request-v1",
        "role": role,
        "model": AGENT_CONFIGS[role]["model"],
        "reasoning_effort": AGENT_CONFIGS[role]["reasoning_effort"],
        "timeout_seconds": AGENT_CONFIGS[role]["timeout_seconds"],
        "input": {
            "task_id": candidate["candidate_id"],
            "prompt_text": candidate["prompt_text"],
            "canonical_skills": canonical_skills,
            "rubric": REVIEW_RUBRIC,
        },
    }
    return {**payload, "request_sha256": canonical_sha256(payload)}
```

- [x] 2.4 Add response validation requiring unique thread/session ID, `fork_context=false`, `history_message_count=0`, `imported_memory_count=0`, exact requested/returned model identity, exact reasoning effort, and transport retry count in `{0,1}`.

- [x] 2.5 Run the request/response tests; expected result is PASS without model/API access.

- [x] 2.6 Commit the request contracts and focused tests.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "feat(router): seal blind-v2 agent request contracts"
```

### Task 3: Replace human-pack validation with three-way unanimous Agent validation

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py:217-618`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:35-186`

- [x] 3.1 Replace `_write_human_pack()` with `_write_agent_pack()` producing 128 accepted test tasks plus optional rejected candidates and exact A/B metadata.

```python
def _candidate(index: int) -> dict[str, Any]:
    gold_index = index // 8
    has_negative = index % 8 < 6
    prompt = f"{PREFIX} REQUEST {index:03d} UNIQUE {index:05d}"
    return {
        "candidate_id": f"opaque-{index:03d}",
        "generation_round": 1,
        "prompt_text": prompt,
        "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "semantic_family_id": f"{PREFIX}_FAMILY_{index:03d}",
        "proposed_gold_skill_id": f"test-skill-{gold_index:02d}",
        "proposed_negative_skill_id": (
            f"test-skill-{(gold_index + 1) % 16:02d}" if has_negative else None
        ),
        "language": "en",
        "rationale": f"{PREFIX} GENERATOR RATIONALE {index:03d}",
    }
```

- [x] 3.2 Add RED tests for exact three-way gold and negative/none agreement, dual `ACCEPT`, rubric booleans, no human fields, and global protocol invalidation on leaked reviewer input.

- [x] 3.3 Implement `validate_agent_pack()` with this signature and fail-closed result shape.

```python
SemanticSimilarity = Callable[[str, str], float]

def validate_agent_pack(
    root: Path | str,
    *,
    repository_root: Path | str,
    canonical_skills: list[dict[str, Any]],
    train_prompts: list[str],
    pilot_prompts: list[str],
    phase16_prompts: list[str],
    train_family_ids: set[str],
    pilot_family_ids: set[str],
    first_read_timestamp: str,
    semantic_similarity: SemanticSimilarity,
) -> dict[str, Any]:
    """Validate sealed Agent ledgers without loading Arm A/C or scoring routes."""
```

- [x] 3.4 Require both reviewers to return `ACCEPT`, `natural=true`, `single_primary_skill=true`, `no_label_leakage=true`, and exact equality with generator gold and negative/none. Require `negative_confusable=true` for a non-null reviewed negative and `negative_confusable=null` for positive-only. Reject disagreements permanently; never adjudicate or use confidence for admission.

- [x] 3.5 Enforce one valid substantive response per role/candidate. Allow a second invocation record only when the first has `transport_failure=true` and no response bytes, with byte-identical request hash/config; reject all other retries.

- [x] 3.6 Run the Agent-pack tests; expected result is PASS and `hasattr(runner, "validate_human_pack") is False`.

- [x] 3.7 Commit the validator conversion.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "feat(router): require unanimous agent blind-v2 review"
```

### Task 4: Implement contamination checks, round limits, and deterministic selection

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py:310-618`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:108-230`

- [x] 4.1 Add RED tests for NFKC/exact overlap, token 5-gram Jaccard `0.80`, character 5-gram Jaccard `0.85`, semantic cosine `0.90`, family overlap, deterministic within-pool conflict winner, round-2 full-pipeline enforcement, and round-3 rejection.

- [x] 4.2 Implement lexical similarity helpers and pin the non-router semantic encoder.

```python
SEMANTIC_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
SEMANTIC_MODEL_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
TOKEN_5GRAM_JACCARD_MAX = Decimal("0.80")
CHARACTER_5GRAM_JACCARD_MAX = Decimal("0.85")
SEMANTIC_COSINE_MAX = Decimal("0.90")

def _jaccard(left: set[str], right: set[str]) -> Decimal:
    if not left and not right:
        return Decimal("1")
    return Decimal(len(left & right)) / Decimal(len(left | right))
```

- [x] 4.3 Implement deterministic conflict precedence: lower generation round first, then lexicographically smaller `selection_key(candidate_id)`; scanner output can only reject and cannot change labels.

- [x] 4.4 Validate round 1 as exactly 256 candidates with 12 negative plus four positive-only proposals per gold skill. Compute round-2 deficits only after scan and dual review; require round-2 candidate count to equal twice each deficit and prohibit any third round.

- [x] 4.5 Select accepted tasks by ascending `selection_key()` within each `(gold_skill_id, negative_or_positive_only)` stratum; require six negative plus two positive-only per skill and 128 unique families.

- [x] 4.6 Run contamination/selection tests twice to prove exact deterministic output.

- [x] 4.7 Commit contamination and selection behavior.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "feat(router): freeze agent blind-v2 selection"
```

### Task 5: Rebuild Commit B documents and complete Agent lineage

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py:619-772,1169-1338,1673-1736`
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation.py:818-866`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:187-387,625-702`
- Modify: `tests/test_router_v2_blind_v2_evaluation.py:369-425`

- [x] 5.1 Add RED tests requiring Commit B to contain final prompt text, 128/96 counts, 128 families, `human_author_count=0`, `human_reviewer_count=0`, exact Agent configuration/prompt/schema/run hashes, retry records, contamination ledger hash, and deterministic selection evidence.

- [x] 5.2 Replace privacy/human branches in `build_dataset_freeze_documents()` with one canonical Agent-generated document shape.

```python
task_rows = [
    {
        "task_id": task["candidate_id"],
        "prompt_text": task["prompt_text"],
        "prompt_text_sha256": task["prompt_text_sha256"],
        "semantic_family_id": task["semantic_family_id"],
        "gold_skill_id": task["proposed_gold_skill_id"],
        "negative_skill_id": task["proposed_negative_skill_id"],
        "source_type": "AGENT_GENERATED",
    }
    for task in validation["tasks"]
]
```

- [x] 5.3 Rename lineage sections from `human_review` to `agent_construction`, bind both reviewer ledgers separately, and include requested/returned models, reasoning efforts, prompt/schema hashes, session IDs, schedule hashes, selection seed, and scanner model/file hashes.

- [x] 5.4 Update `build_evaluation_documents()` report wording and denominators to 128/96; remove every human-reviewed/generalization claim and include the same-provider limitation.

- [x] 5.5 Re-run freeze, lineage, report, and exact-byte regeneration tests; expected result is PASS and no raw rationale/hidden reasoning in Commit B bytes.

- [x] 5.6 Commit freeze and lineage changes.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  tests/test_router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "feat(router): bind agent blind-v2 dataset lineage"
```

### Task 6: Repair Git authority and smoke ordering

**Files:**
- Modify: `src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py:217-278,832-1168,1339-1564`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:269-624`

- [x] 6.1 Add RED tests proving the old human commit cannot authorize generation, Commit A-agent must supersede it, Commit B is its direct child with only three dataset files, Agent-config smoke is pre-generation, and A/C model smoke requires both Commit A-agent and Commit B.

- [x] 6.2 Replace the one-commit-above-main assertion with explicit supersession ancestry and changed-file authority.

```python
HISTORICAL_HUMAN_COMMIT_A = "09ba4104a147a2f740ef69283c850f40e78a0b15"

def validate_commit_a_repository(
    repository_root: Path | str,
    preregistration: dict[str, Any],
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(_git(repository, "status", "--porcelain", "--untracked-files=all") == "", "Commit A-agent worktree must be clean")
    head = _git(repository, "rev-parse", "HEAD")
    origin_main = _git(repository, "rev-parse", "origin/main")
    _require(origin_main == PREREGISTRATION_PARENT_COMMIT, "origin/main drift")
    _require(preregistration["supersedes_commit"] == HISTORICAL_HUMAN_COMMIT_A, "supersession mismatch")
    _require(_git(repository, "merge-base", "--is-ancestor", HISTORICAL_HUMAN_COMMIT_A, head) == "", "historical Commit A must be an ancestor")
    _require(head != HISTORICAL_HUMAN_COMMIT_A, "historical Commit A is not active")
    return {"commit_a": head, "origin_main": origin_main, "supersedes_commit": HISTORICAL_HUMAN_COMMIT_A}
```

- [x] 6.3 Add `build_agent_config_smoke_receipt()`/validation for three dummy-text invocations bound to Commit A-agent and preregistration hash. This receipt is required before staged request generation.

- [x] 6.4 Change A/C model-smoke receipt to bind `commit_a`, `commit_b`, preregistration hash, and frozen dataset manifest hash; refuse to run or validate it on Commit A-agent alone.

- [x] 6.5 Keep Arm A/C smoke internals unchanged except schema/order binding; still load one A and three C models on CPU, encode only the two synthetic strings, and delete temporary files.

- [x] 6.6 Run Git authority and smoke tests; expected result is PASS with no actual model download.

- [x] 6.7 Commit authority/smoke changes.

```bash
git add src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "fix(router): enforce agent blind-v2 commit barriers"
```

### Task 7: Expose only the narrow Agent workflow through the CLI

**Files:**
- Modify: `scripts/run_router_v2_blind_v2_final.py:1-346`
- Modify: `tests/test_router_v2_blind_v2_evaluation_runner.py:757-835`

- [x] 7.1 Add RED CLI tests for these commands only: `agent-config-status`, `request-round-1`, `request-reviews`, `request-round-2`, `pack-status`, `freeze`, `model-smoke`, and `evaluate`.

- [x] 7.2 Remove `write_authoring_templates`, human-pack imports, human status, and old pre-data `smoke`. Rename loader helpers to Agent terminology.

- [x] 7.3 Implement command order guards:

```text
Commit A-agent
  -> agent-config-status
  -> request-round-1
  -> request-reviews
  -> optional request-round-2 + request-reviews
  -> pack-status
  -> freeze
Commit B
  -> model-smoke
  -> evaluate
```

- [x] 7.4 Ensure request commands derive all prompts, schemas, skills, staging root, and quotas from preregistered authority; caller options may select only a frozen stage or reviewer role and may not inject labels, model names, paths, thresholds, seeds, or output directories.

- [x] 7.5 Preserve the CLI ban on `train`, `mine`, `tune`, `attempt-2`, `blind-v2-002`, and `blind-v3`.

- [x] 7.6 Run CLI help and focused runner tests; expected result is PASS.

- [x] 7.7 Commit the CLI conversion.

```bash
git add scripts/run_router_v2_blind_v2_final.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "feat(router): expose sealed agent blind-v2 workflow"
```

### Task 8: Rewrite protocol and preregistration as the final pre-data authority

**Files:**
- Modify: `docs/router-v2-blind-v2-protocol.md:1-267`
- Modify: `artifacts/router-v2-blind-v2/preregistration.json:1-480`
- Modify: `openspec/changes/run-router-v2-final-blind-v2/{proposal.md,design.md,tasks.md,specs/router-v2-final-blind-v2/spec.md}` only if implementation names differ from the approved contract

- [x] 8.1 Replace every active human 64/48, publication-permission, human-review, and waiting-for-human state with the approved Agent 128/96 contract while retaining a clearly historical supersession note.

- [x] 8.2 Embed this canonical generator system prompt and its JSON schema verbatim in protocol and preregistration.

```text
You are the Generator for a preregistered Router V2 blind evaluation. Create natural English user requests for exactly one primary canonical skill. Do not mention skill IDs, skill names, gold labels, negative labels, benchmarks, routers, training, pilot data, Phase 16, Arm A, Arm C, or model behavior. For a negative-labeled candidate, choose one plausible but insufficient canonical negative skill. Use only the supplied skill definitions and quota. Do not use external memory or prior conversation. Return only JSON matching the supplied schema.
```

```json
{
  "candidates": [
    {
      "candidate_index": 0,
      "prompt_text": "natural English request",
      "semantic_family_id": "opaque family string",
      "proposed_gold_skill_id": "canonical skill id",
      "proposed_negative_skill_id": "canonical skill id or null",
      "language": "en",
      "rationale": "brief label rationale"
    }
  ]
}
```

The frozen response requires exactly 16 candidate objects for each round-1 skill request. The controller, not the Generator, assigns each opaque ID as the first 24 hex characters of `sha256(f"{round_number}:{skill_id}:{candidate_index}:{response_sha256}")`.

- [x] 8.3 Embed this canonical reviewer system prompt and schema verbatim for both reviewer roles.

```text
You are a role-isolated reviewer for one preregistered Router V2 blind candidate. Use only the supplied task text, canonical skill definitions, and rubric. Independently decide the single primary gold skill and one plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural wording, label leakage, invalid negatives, and tasks with more than one equally primary skill. Do not use external memory, prior conversation, quotas, other reviews, generator labels, Router models, or model results. Return only JSON matching the supplied schema.
```

```json
{
  "decision": "ACCEPT or frozen REJECT code",
  "reviewed_gold_skill_id": "canonical skill id",
  "reviewed_negative_skill_id": "canonical skill id or null",
  "natural": true,
  "single_primary_skill": true,
  "no_label_leakage": true,
  "negative_confusable": null,
  "confidence": "LOW, MEDIUM, or HIGH",
  "reason": "brief decision rationale"
}
```

`negative_confusable` is `true` when `reviewed_negative_skill_id` is non-null and is `null` when the reviewer independently selects no negative.

- [x] 8.4 Record exact configs, timeouts, response schemas, transport-only retry, round quotas, reviewer schedule hashes, all-mpnet revision/file hashes, 0.80/0.85/0.90 thresholds, selection seed/order, terminal states, and `blind_v2_candidate_data_seen=false`.

- [x] 8.5 Recompute every evaluator, skill, frozen-input, gate, prompt, schema, semantic-model, and preregistration canonical hash. Assert old model/checkpoint/training/pilot hashes are byte-identical.

- [x] 8.6 Run focused tests and preregistration authority validation before any Agent invocation.

### Task 9: Validate and create the superseding Commit A-agent

**Files:**
- All files listed in Tasks 1-8; no data, README, resume, historical pilot, training, or final-attempt files

- [x] 9.1 Run the focused blind-v2 suites.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q \
  tests/test_router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
```

Expected: all focused tests pass.

- [x] 9.2 Run static validation.

```bash
ruff check src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  scripts/run_router_v2_blind_v2_final.py \
  tests/test_router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
ruff format --check src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  scripts/run_router_v2_blind_v2_final.py \
  tests/test_router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
mypy src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  scripts/run_router_v2_blind_v2_final.py
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
git diff --check
```

Expected: every command exits 0.

- [x] 9.3 Run the full suite, record the exact fresh pass/fail counts, and attribute only failures introduced by the current diff; do not hide the frozen `origin/main` baseline failures.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q
```

- [x] 9.4 Dispatch a read-only Reviewer over the complete pre-data diff. Required verdict format:

```text
Must Fix:
Should Fix:
Nice to Have:
Re-plan Needed: Yes / No
Final Verdict: Pass / Pass with fixes / Blocked
```

- [x] 9.5 Fix only in-scope Must Fix items, rerun fresh validation, confirm `HERMES_BLIND_V2_ROOT` has not been read, and confirm no Arm A/C model has loaded under the new protocol.

- [x] 9.6 Create the final superseding preregistration commit and record its SHA.

```bash
git add openspec/changes/run-router-v2-final-blind-v2 \
  docs/router-v2-blind-v2-protocol.md \
  artifacts/router-v2-blind-v2/preregistration.json \
  src/hermes_skilleval/router_v2_blind_v2_evaluation.py \
  src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py \
  scripts/run_router_v2_blind_v2_final.py \
  tests/test_router_v2_blind_v2_evaluation.py \
  tests/test_router_v2_blind_v2_evaluation_runner.py
git commit -m "docs(router): preregister agent-only Router V2 blind-v2"
git status --short
git show --stat --oneline HEAD
git rev-parse HEAD
```

Expected: clean worktree; HEAD is Commit A-agent and descends from `09ba4104…`.

### Task 10: Run the Agent-configuration smoke under the active Goal

**Files:**
- Create outside Git: `/Users/raidriar/.codex/private/hermes-blind-v2/${COMMIT_A_SHA}/agent-run-metadata.json`
- Create outside Git: Commit A-agent-bound Agent configuration smoke receipt

- [ ] 10.1 Confirm the active Goal still covers Tasks 1-14 and preserves all Commit A-agent/Commit B/single-attempt stop conditions and prohibited actions.

- [ ] 10.2 Set `HERMES_BLIND_V2_ROOT` to the absolute private root for Commit A-agent and verify it is outside every Git worktree.

```bash
COMMIT_A_SHA=$(git rev-parse HEAD)
export HERMES_BLIND_V2_ROOT="/Users/raidriar/.codex/private/hermes-blind-v2/${COMMIT_A_SHA}"
```

- [ ] 10.3 Spawn three fresh non-forked dummy-text invocations with exact overrides:

```text
Generator:  model=gpt-5.6-sol,  reasoning=max,   fork_context=false
Reviewer A: model=gpt-5.6-sol,  reasoning=ultra, fork_context=false
Reviewer B: model=gpt-5.6-luna, reasoning=max,   fork_context=false
```

- [ ] 10.4 Record requested/returned model IDs, reasoning efforts, unique run/thread IDs, empty-history/no-memory declarations, request/response hashes, timestamps, and retry count. Validate with `agent-config-status`; stop at `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` plus `KEEP_BASELINE` on any mismatch.

### Task 11: Generate, scan, and dual-review the candidate pool

**Files:**
- Create outside Git: the five required `HERMES_BLIND_V2_ROOT` ledger files
- No repository or Arm A/C file access beyond frozen skill/reference inputs

- [ ] 11.1 Use `request-round-1` to produce 16 sealed generator requests, one per gold skill, each requesting 12 negative-labeled plus four positive-only candidates. Spawn each with `gpt-5.6-sol/max`, `fork_context=false`, and no thread history.

- [ ] 11.2 Canonicalize and hash exactly 256 returned candidate rows; reject malformed outputs without a substantive retry and record transport-only retries exactly.

- [ ] 11.3 Run static/lexical/all-mpnet contamination scanning against train, pilot-002, Phase 16, and within-pool candidates. Seal `blind-v2-contamination.jsonl`; never send scan results or rejection reasons to an Agent.

- [ ] 11.4 For every clean candidate, call `request-reviews` and spawn Reviewer A and Reviewer B as separate one-candidate, non-forked, empty-history sessions in their independently hashed schedules. Never fork, reuse, or resume a reviewer session.

- [ ] 11.5 Seal both review ledgers before comparison. Mechanically compute exact three-way agreement and dual `ACCEPT`; do not adjudicate, relabel, or select by confidence.

- [ ] 11.6 If any `(gold skill, negative/positive-only)` stratum is short, use `request-round-2` once for exactly twice the deficit. Send every new candidate through the complete scan and two-new-reviewer-session path. If any stratum remains short, write `AGENT_BLIND_V2_DATASET_INSUFFICIENT` plus `KEEP_BASELINE` and stop before Commit B.

- [ ] 11.7 Run `pack-status` and verify exactly 128 selected tasks, 96 negatives, 128 families, zero human counts, expected Agent configs, no protocol leak, and no Arm A/C score/model load.

### Task 12: Freeze and commit the selected dataset as Commit B

**Files:**
- Create: `data/router-v2-blind-v2/blind-v2-tasks.jsonl`
- Create: `data/router-v2-blind-v2/blind-v2-review-summary.json`
- Create: `data/router-v2-blind-v2/blind-v2-manifest.json`

- [ ] 12.1 Run `freeze` from clean Commit A-agent and verify exact-byte regeneration twice.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python scripts/run_router_v2_blind_v2_final.py freeze
```

- [ ] 12.2 Verify Commit B content contains only the canonical three files, all final prompts, sanitized Agent evidence/hashes, `model_scores_observed=false`, `evaluation_started=false`, and no raw hidden reasoning.

- [ ] 12.3 Commit the byte-bound dataset and record Commit B SHA.

```bash
git add data/router-v2-blind-v2
git commit -m "data(router): freeze dual-agent-reviewed Router V2 blind-v2"
git diff --name-only HEAD^..HEAD
git status --short
git rev-parse HEAD
```

Expected: exactly three changed paths and a clean worktree.

### Task 13: Run the post-Commit-B A/C smoke and unique formal attempt

**Files:**
- Create worktree: `/Users/raidriar/dev/hermes-skilleval-worktrees/router-v2-blind-v2-attempt-1`
- Create: `artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/attempt-1/**`

- [ ] 13.1 Create a fresh detached worktree at Commit B and verify clean status, Commit A-agent/Commit B ancestry, dataset hash, namespace absence, and marker absence.

```bash
git worktree add --detach \
  /Users/raidriar/dev/hermes-skilleval-worktrees/router-v2-blind-v2-attempt-1 \
  "$(git rev-parse HEAD)"
```

- [ ] 13.2 Run `model-smoke` only now. It must bind Commit A-agent and Commit B, load one A plus three C models on CPU, encode only fixed synthetic strings, remove temporary files, and emit no benchmark metric.

- [ ] 13.3 Revalidate every hash, count, smoke receipt, output namespace, protected root, seed, gate, and clean-worktree condition before writing the exclusive started marker.

- [ ] 13.4 Run `evaluate` once. Never create attempt-2, retry a seed, delete a marker, replace a task, or alter a gate after the marker.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python scripts/run_router_v2_blind_v2_final.py evaluate
```

- [ ] 13.5 Verify all result documents, raw counts over 128/96, per-seed/aggregate/statistical consistency, lineage self-hash, and exactly one terminal status. Every path must contain `KEEP_BASELINE` and unchanged production/release/default fields.

### Task 14: Close out, review, commit, push, and open one PR

**Files:**
- Conditionally modify: `README.md`, `README_EN.md`, `docs/resume.md`, `docs/interview-project-overview.html`
- Add final result artifacts only under the canonical namespace

- [ ] 14.1 Update public surfaces only for `AGENT_BLIND_V2_GATES_PASSED` or `AGENT_BLIND_V2_GATES_NOT_PASSED`; leave them unchanged for pre-evaluation terminal states. Use Agent-set-bounded language, exact model configs, raw counts, same-provider limitation, and `KEEP_BASELINE`.

- [ ] 14.2 Run focused tests, full tests, Ruff, mypy, OpenSpec strict validation, `git diff --check`, frozen-artifact hash guards, no-training guards, one-attempt checks, and report/artifact number consistency.

- [ ] 14.3 Obtain final read-only Reviewer verdict. Fix only presentation or validation defects that cannot alter tasks, labels, models, checkpoints, gate, metrics, or results.

- [ ] 14.4 Commit terminal artifacts and any authorized result-facing documents without rewriting Commit A-agent or Commit B.

- [ ] 14.5 Push `agent/router-v2-blind-v2-final` and open one PR. Do not merge, tag, release, deploy, archive, or change the default router.

- [ ] 14.6 Report the final status, Commit A-agent, Commit B, attempt marker/terminal state, per-seed and aggregate results, statistics, gate, `KEEP_BASELINE`, validation evidence, artifact hashes, explicit non-actions, and limitations; then stop Hermes optimization permanently.
