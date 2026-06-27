# Hermes SkillEval v0.3 Codex Implementation Guide

Status: PR-0 guidance only

Date: 2026-06-27

This guide gives Codex the detailed execution brief for PR-1 through PR-7.
It is subordinate to `docs/v0.3/protocol.md` and does not implement any of the
later PRs. PR-0 remains documentation, OpenSpec, and placeholder configuration
only.

## Global Rules For PR-1 Through PR-7

- Work one PR scope at a time.
- Read `AGENTS.md`, `CONTEXT.md`, `README.md`, `docs/v0.3/protocol.md`, this
  guide, the active OpenSpec artifacts, and the nearest existing code/tests
  before editing.
- Preserve existing CLI behavior and historical Phase 10 through Phase 18
  artifacts unless a future approved change explicitly updates them.
- Treat SkillRouter final scored labels as evaluation-only: no training,
  threshold tuning, model selection, variant selection, task filtering, or
  hard-negative mining on those labels.
- Keep official SkillRouter metrics separate from Hermes diagnostics.
- Do not compute Hermes Negative Hit Rate or Negative Accepted Rate on external
  data without explicit negative labels.
- Keep Phase 10 as deterministic offline replay. Do not describe it as
  live-agent evidence.
- Use deterministic verifiers as the primary live-agent success judge.
- Keep Benchmark Validity Gate statuses separate from Router Promotion Gate
  decisions.
- Use `UNAVAILABLE` only as a field-level marker with a reason; do not emit it
  as a top-level Benchmark Validity Gate status.
- Use literal artifact roots such as `artifacts/v0.3/{run_id}/`; avoid
  placeholder expansions that can render an empty run-id artifact root.
- Do not commit external full datasets, model checkpoints, embedding caches,
  credentials, raw auth files, private host details, raw traces, or unredacted
  logs.

## PR-1: External Adapter And Provenance

Goal: create a canonical external benchmark adapter and SkillRouter loader
without model inference or scoring.

Expected work:

- Define canonical task, skill, adapter, and provenance structures.
- Load SkillRouter tasks, relevance labels, and Easy/Hard skill shards from a
  config-provided data root.
- Support `.jsonl`, `.jsonl.gz`, and shard directories.
- Stream skill shards rather than loading the full skill corpus eagerly.
- Preserve unknown upstream fields in metadata.
- Validate duplicate task IDs, duplicate skill IDs, empty queries, missing
  relevance, missing gold skills, corrupt gzip input, and tier mismatches.
- Record upstream ref, file SHA-256 hashes, adapter mapping, license notes, and
  acquisition metadata.
- Add tiny offline fixtures under `tests/fixtures/`; never download full data
  in CI.

Acceptance:

- Tiny fixtures validate offline and deterministically.
- Full external data is not committed.
- Adapter failures are explicit and actionable.
- Existing tests remain green.

Validation:

```bash
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
git diff --check
```

## PR-2: Official Metrics And Scorer Parity

Goal: reproduce SkillRouter official scoring semantics and keep Hermes
diagnostics separate.

Official metrics:

- `nDCG@1`, `nDCG@3`, `nDCG@10`
- `Hit@1`
- `Precision@3`
- `MRR@10`
- `Recall@10`, `Recall@20`, `Recall@50`
- `FullCoverage@3`, `FullCoverage@5`, `FullCoverage@10`

Required dimensions:

- `all`
- `single`
- `multi`
- per selected candidate skill pool tier: `easy` and `hard`

Expected work:

- Use graded relevance for NDCG.
- Skip missing task predictions for SkillRouter official scorer parity.
- Fix and test the duplicate prediction strategy before any full run.
- Put invalid skill IDs, duplicate IDs, missing predictions, candidate counts,
  field views, latency, and router IDs in Hermes diagnostics.
- Write official metrics and Hermes diagnostics to separate outputs.
- Add optional upstream official-scorer parity when `SKILLROUTER_REPO` is set.
- Make parity failure return non-zero.

Acceptance:

- Tiny fixtures have hand-computable exact assertions.
- Official and Hermes namespaces are not mixed.
- No GPU, network, or sentence-transformer dependency is required for scoring
  tests.

## PR-3: Frozen Routing Matrix And Generalization Checks

Goal: run frozen routers without scored-label tuning and produce external
routing evidence with deterministic diagnostics.

Human brief: `docs/human-briefs/2026-06-27-external-matrix-generalization.html`

Expected work:

- Generate a frozen evaluation plan before running scored evaluation.
- Compare at minimum `baseline-minilm` and `finetuned-embedding`.
- Record router ID, checkpoint/model revision/hash, text builder,
  normalization, top-k, rerank depth, threshold, runtime version, and git
  commit.
- Evaluate `name_only`, `metadata`, and `full_body` field views.
- Use full Easy/Hard pools for official results.
- Use 1K, 10K, and full candidate pools only as Hermes stress tests.
- Include every relevant skill before distractors; mark a subset
  `UNAVAILABLE` when the target size cannot contain the relevant-skill union.
- Select distractors by `sha256("20260625:" + skill_id)`.
- Implement held-out-skill split using task/gold-skill connected components.
- Implement held-out-source only when source metadata is sufficient; otherwise
  write field-level `UNAVAILABLE` with a reason.
- Implement SkillRouter-to-live-task overlap reporting by ID and normalized
  text hash, with room for high-similarity diagnostics.
- Implement paired bootstrap 95% confidence intervals using task-level paired
  deltas and seed `20260625`.

Acceptance:

- Formal runs have a frozen plan and unique run ID.
- Candidate subset hashes are recorded.
- Split overlap assertions fail closed.
- Stress tests are not described as official SkillRouter results.

## PR-4: Live-Agent Runtime Abstraction And Fake Runner

Goal: build a testable `live-agent.v1` contract without invoking a real Codex
or SkillsBench process.

Human brief: `docs/human-briefs/2026-06-28-live-agent-runtime-fake.html`

Expected work:

- Add request/result structures and an `AgentRunner` protocol.
- Define `no-skill`, `routed-skill`, and `oracle-skill` condition builders.
- Keep prompts identical across conditions; only skill injection differs.
- Create a fresh workspace for each run and fail on workspace reuse.
- Separate process exit status from verifier success.
- Define and validate `live-agent.v1` trace schema.
- Record mounted skill IDs and hashes.
- Represent skill use as `READ`, `DECLARED`, `MOUNTED_ONLY`, or `UNKNOWN`
  according to observable events.
- Treat usage/cost as `null` or field-level `UNAVAILABLE` when not reliably
  available.
- Add fake-runner tests for success, verifier failure, process failure,
  timeout, malformed events, unknown events, secret redaction, log truncation,
  no-skill leakage, and workspace reuse.

Acceptance:

- CI does not require Codex CLI, Docker, network, or external services.
- Phase 10 schemas and `live-agent.v1` are clearly separate.
- Verifier pass is the only task-success source.

## PR-5: Codex CLI Runner And Isolation

Goal: implement a real Codex CLI runner with strict isolation, redaction, and
trace parsing.

Expected work:

- Read the local `codex exec --help` and record the actual supported flags.
- Use non-interactive execution with ephemeral sessions, workspace-write
  sandboxing, approval policy never, JSONL events, and final-message capture
  when supported by the installed CLI.
- Never use `--yolo` or danger-full-access for benchmark evidence.
- Support isolated and inherited `CODEX_HOME` modes; final evidence defaults
  to isolated mode.
- Preflight global skills, plugins, MCP, and config leakage.
- Mount benchmark skills under a workspace-local skill directory.
- Keep `no-skill` free of benchmark/global skills.
- Parse JSONL events for tool calls, file reads, `SKILL.md` reads, final
  messages, token usage when reliable, and unknown event types.
- Kill the full process group on timeout.
- Redact secrets, authorization headers, private paths where needed, and
  private host details.
- Test against a fake Codex executable before any manual smoke run.

Acceptance:

- Mock CLI tests cover success, timeout, leakage, malformed JSONL, unknown
  events, and redaction.
- A minimal manual smoke can run after validity checks, but it is not benchmark
  evidence.

## PR-6: SkillsBench Adapter And Live Matrix

Goal: select, freeze, and run deterministic no-credential live-agent tasks.

Expected work:

- Pin a SkillsBench upstream commit and record repo, commit, task directory
  hash, version/help snapshots, and license notes.
- Use upstream CLI or harness commands as verified at that pinned commit; do
  not guess command names.
- Select tasks that require no credentials, default to no network, have stable
  deterministic verifiers, and pass oracle qualification.
- Cover multiple domains and include both single-skill and multi-skill tasks
  when available.
- Check overlap against SkillRouter by exact ID and normalized text hash before
  claiming independent evidence.
- Freeze selected tasks before pilot or final results are inspected.
- Build a global E2E skill registry across tasks and distractors; do not route
  only within each task's own skills.
- Hide task IDs and gold labels from exposed skill names and prompts.
- Generate a block-randomized run order by task using seed `20260625`.
- Run pilot separately from frozen evaluation.
- Count pass/fail only from deterministic verifier records.
- Bootstrap over tasks, not individual repeated trials.

Acceptance:

- Task manifest, registry manifest, overlap report, run order, traces,
  verifier records, and summaries are present for each counted run.
- `no-skill`, `routed-skill`, and `oracle-skill` prompts have matching hashes.
- Raw traces are not committed unless redacted and explicitly allowed.

## PR-7: Evidence Validator And Conservative Decision Packet

Goal: combine external and live-agent evidence into a conservative decision
packet without automatic overpromotion.

Expected work:

- Implement Benchmark Validity Gate independently from Router Promotion Gate.
- Make validity produce only `VALID_EVIDENCE`, `INVALID_EVIDENCE`, or
  `REVIEW_REQUIRED`.
- Use `UNAVAILABLE` only for individual missing fields/checks with reasons.
- Block promotion when validity is `INVALID_EVIDENCE`.
- Default to `KEEP_BASELINE` unless a future preregistered promotion gate is
  satisfied.
- Report absolute metrics, paired deltas, confidence intervals, Easy/Hard,
  single/multi, per-task live-agent outcomes, oracle gaps, regressions,
  timeout/cost/failure taxonomy, and overlap caveats.
- Mark linked-transfer evidence when overlap prevents independent
  generalization claims.
- Update `docs/evidence-map.md` only with committed, redacted, reproducible
  evidence.

Acceptance:

- Decision table tests cover validity failures, conflicting evidence, linked
  transfer, live task regression, timeout increase, and default
  `KEEP_BASELINE`.
- Reports do not contain resume/public-facing numeric claims unless the
  supporting artifacts exist.

## Formal Stop Conditions

Stop the active phase, record `REVIEW_REQUIRED` or `INVALID_EVIDENCE`, and do
not continue the formal run when:

- official scorer parity fails;
- relevant skills are missing from a required tier without upstream policy;
- scored labels influence training, threshold selection, or model selection;
- candidate subsets drop relevant skills;
- held-out split overlap is detected;
- no-skill sees benchmark/global skills;
- condition prompt hashes differ;
- oracle qualification is unstable;
- verifier behavior is random or credential-dependent;
- the agent can read solutions, oracle internals, gold labels, or verifier
  answers;
- overlap is present but the report still claims independent evidence;
- trace core fields are missing;
- secret scan fails;
- the runner requires unsafe sandboxing;
- upstream refs are not pinned;
- poor-performing tasks are replaced after results are inspected.

## Standard Validation Footer

Each PR must document which of these commands ran and why any command was not
applicable:

```bash
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
git diff --check
```

PRs that change YAML under `configs/v0.3/` must also parse those files before
completion.
