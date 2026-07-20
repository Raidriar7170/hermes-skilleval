## ADDED Requirements

### Requirement: Agent-only protocol and evaluator are frozen before candidate generation
The system SHALL create a superseding Commit A-agent before generating any blind-v2 candidate. Commit A-agent SHALL retain historical commit `09ba4104a147a2f740ef69283c850f40e78a0b15` as audit history, declare it non-authoritative through `supersedes_commit`, and bind current `origin/main`, exact Arm A/C identities and files, frozen training inputs, query and skill-representation contracts, evaluator paths and hashes, unchanged pilot-002 gate, verbatim Agent prompts and schemas plus their SHA-256 hashes, exact Agent configurations and timeouts, isolation/retry/contamination/selection rules, expected `128`/`96` counts, single-attempt policy, and all prohibited post-data actions. Generator timeout SHALL be `1800` seconds; each reviewer timeout SHALL be `900` seconds; selection seed SHALL be `7170` with ascending lexicographic SHA-256 ordering.

#### Scenario: Commit A-agent is created without candidate data
- **WHEN** the superseding preregistration is prepared from frozen repository and model authority
- **THEN** `blind_v2_candidate_data_seen` is `false`, the evaluator and Agent construction contract are frozen in the same commit, and no candidate or review source file has been opened

#### Scenario: Historical Commit A is presented as active
- **WHEN** a generation, freeze, or evaluation command is bound only to historical commit `09ba4104…`
- **THEN** the system refuses to proceed and reports that the human-pack protocol has been superseded

#### Scenario: Frozen authority drifts
- **WHEN** any model, checkpoint, manifest, seed, training input, skill index, query contract, skill representation, gate, prompt, schema, Agent configuration, contamination rule, selection rule, or evaluator hash differs from Commit A-agent
- **THEN** the system stops before candidate generation or model scoring and performs no repair, fallback, retraining, or replacement

### Requirement: Smokes verify Agent configurations before generation and A/C models after Commit B
The system SHALL run two non-benchmark smokes bound to Commit A-agent: an Agent-configuration smoke before candidate generation using dummy text for Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max`; and, only after clean Commit B, the fixed-string CPU model-load smoke for Arm A and Arm C seeds `7170`, `7171`, and `7172`.

#### Scenario: Every required configuration and model passes
- **WHEN** requested and returned Agent identities/reasoning efforts match before generation and each A/C model later passes file verification, load, encode, dimension, and finite-value checks on Commit B
- **THEN** both smoke receipts bind Commit A-agent, the A/C receipt also binds Commit B, and neither smoke computes benchmark metrics or writes an evaluation attempt

#### Scenario: A required configuration is unavailable
- **WHEN** any exact Agent alias or reasoning effort cannot be invoked or the returned model identity violates the frozen contract
- **THEN** the system records `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` with `failure_stage=agent_config_smoke`, uses no fallback model, and generates no candidate

#### Scenario: An A/C model fails smoke
- **WHEN** any required Arm A/C model cannot be verified, loaded, or encoded
- **THEN** the system records `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` with `failure_stage=ac_model_smoke`, keeps `KEEP_BASELINE`, and stops before the formal attempt without changing Commit B

### Requirement: Candidate generation is sealed and bounded to two rounds
The system SHALL use Generator `gpt-5.6-sol` with reasoning effort `max`. Round 1 SHALL contain exactly 256 candidates: 16 per gold skill, comprising 12 negative-labeled proposals and four positive-only proposals per skill. The generator SHALL receive only canonical skill definitions, naturalness/single-primary-skill/leakage rules, and frozen quotas, and MUST NOT receive train, pilot-002, Phase 16, Arm A/C, review, contamination, or model-result content.

#### Scenario: First-round generation succeeds
- **WHEN** the generator returns a syntactically valid structured response under the frozen model and prompt hashes
- **THEN** the controller seals exactly 256 candidate records with opaque IDs, round, prompt, semantic family, proposed gold, proposed negative/none, language, concise rationale, requested/returned model identity, reasoning effort, run ID, and response hash

#### Scenario: Accepted strata remain short after round 1
- **WHEN** deterministic filtering and unanimous review leave one or more gold-skill and negative/positive-only strata below final quota
- **THEN** the system permits exactly one round-2 request for twice each numeric stratum deficit and reveals no rejected prompt, rejection reason, reviewer label, contamination score, or Arm A/C output

#### Scenario: A second replenishment is requested
- **WHEN** round 2 has already produced a syntactically valid response
- **THEN** the system rejects every further generation request and does not lower the final quota or review standard

### Requirement: Two reviewers are role-isolated and unanimously accept every selected task
The system SHALL review each contamination-clean candidate in two separate fresh, non-forked, one-candidate sessions: Reviewer A using `gpt-5.6-sol/ultra` and Reviewer B using `gpt-5.6-luna/max`. Every invocation SHALL have a unique thread/session ID, empty history, no imported memory payload, and a request-schema whitelist containing only opaque task ID, prompt, canonical skill definitions, and frozen rubric. Reviewer A SHALL be scheduled by ascending `sha256("review-a:7170:" + candidate_id)` and Reviewer B by ascending `sha256("review-b:7171:" + candidate_id)`. A reviewer MUST NOT receive generator labels/rationale, the other review, quotas/deficits, prior candidates, contamination output, or Arm A/C information.

#### Scenario: Three-way agreement accepts a candidate
- **WHEN** both reviewers independently emit `ACCEPT`, independently affirm naturalness, a single primary skill, no leakage, and valid negative confusability when applicable, and the generator plus both reviewers choose exactly the same gold and negative-skill/none labels
- **THEN** the candidate is eligible for deterministic final selection

#### Scenario: Any label or rubric judgment disagrees
- **WHEN** either reviewer rejects, labels differ, negative/none differs, or a required rubric assertion is false
- **THEN** the candidate is permanently rejected without adjudication, majority vote, feedback, relabeling, or repeat review

#### Scenario: A reviewer receives prohibited context
- **WHEN** a review request includes generator labels, another review, quota state, prior candidate context, contamination output, or Router results
- **THEN** the system globally terminates at `AGENT_BLIND_V2_PROTOCOL_INVALID`, records `KEEP_BASELINE`, and forbids Commit B and all model scoring

### Requirement: Agent retries are transport-only
The system SHALL permit at most one retry for an Agent invocation only when no syntactically valid response was received because of a recorded transport failure. The retry SHALL use byte-identical input, prompt hash, model alias, and reasoning effort.

#### Scenario: Transport fails before a response
- **WHEN** a call ends with a recorded transport failure and no valid response bytes
- **THEN** exactly one identical retry is allowed and both attempts are recorded in lineage

#### Scenario: A substantive response is invalid or rejected
- **WHEN** a response has the wrong model identity, invalid schema, refusal, rubric rejection, or label disagreement
- **THEN** no retry, fallback model, lower reasoning effort, prompt repair, or second opinion is allowed

### Requirement: Non-voting contamination checks precede review
The system SHALL apply UTF-8/schema validation, unique prompt bytes, NFKC-casefold normalization, exact hashes, token 5-gram Jaccard `>= 0.80`, character 5-gram Jaccard `>= 0.85`, family-ID disjointness, and normalized-embedding cosine similarity `>= 0.90` against train, pilot-002, Phase 16, and prior/current blind-v2 candidates before review. Semantic embeddings SHALL use prompt-only text and `sentence-transformers/all-mpnet-base-v2` at revision `e8c3b32edf5434bc2275fc9bab85f82640a19130` with all materialized file hashes bound in Commit A-agent. The semantic checker MUST NOT use Arm A, Arm C, or another evaluated checkpoint.

#### Scenario: Candidate is clean
- **WHEN** a candidate passes every frozen schema, leakage, duplicate, family, and semantic-overlap rule
- **THEN** it may be sent to the two reviewers without exposing scanner outputs

#### Scenario: Candidate overlaps protected data or another candidate
- **WHEN** any exact, normalized, lexical, family, or semantic threshold is violated
- **THEN** the scanner deterministically rejects the candidate, records the evidence hash, assigns no label, and sends no rejection detail to Generator or reviewers

#### Scenario: Two current candidates conflict
- **WHEN** two candidates violate a frozen within-set overlap rule
- **THEN** the lower generation round wins, followed by the lexicographically smaller `sha256("7170:" + candidate_id)`, and the other candidate is rejected

### Requirement: Static validation deterministically selects a 128/96 set before model scoring
The system SHALL derive the final set only from contamination-clean, three-way-unanimous candidates from either round. Every round-2 candidate SHALL pass the same full contamination scan, fresh Reviewer A session, fresh Reviewer B session, dual `ACCEPT`, and exact three-way label agreement as round 1. The system SHALL select by ascending lexicographic `sha256("7170:" + candidate_id)` within each gold-skill and negative/positive-only stratum, and SHALL require exactly 128 tasks, 16 gold skills with eight tasks each, six negative-labeled plus two positive-only tasks per gold skill, 96 total negative labels, and 128 distinct task IDs, prompt bytes, normalized prompts, and semantic families.

#### Scenario: A valid accepted pool exists
- **WHEN** all 16 gold-skill strata contain at least six negative-labeled and two positive-only unanimous candidates after at most two rounds
- **THEN** deterministic hash order selects exactly 128 tasks without consulting confidence, rationale, reviewer preference, or Arm A/C behavior

#### Scenario: A final stratum remains short
- **WHEN** any skill/type stratum or uniqueness rule cannot be satisfied after round 2
- **THEN** the workflow reports `AGENT_BLIND_V2_DATASET_INSUFFICIENT`, records deficits and ledger hashes, and performs no Commit B or model scoring

#### Scenario: Selection input or rule drifts
- **WHEN** the accepted pool hash, selection seed, ordering rule, or quota differs from Commit A-agent
- **THEN** the workflow reports `AGENT_BLIND_V2_PROTOCOL_INVALID` and freezes no dataset

### Requirement: Commit B freezes Agent-reviewed data and sanitized lineage before scoring
The system SHALL read raw construction evidence only from an absolute `HERMES_BLIND_V2_ROOT` outside every Git worktree containing `blind-v2-generation.jsonl`, `blind-v2-review-a.jsonl`, `blind-v2-review-b.jsonl`, `blind-v2-contamination.jsonl`, and `agent-run-metadata.json`. After static validation it SHALL create `blind-v2-tasks.jsonl`, `blind-v2-review-summary.json`, and `blind-v2-manifest.json` under `data/router-v2-blind-v2/`, then create Commit B as a direct child of Commit A-agent before Arm A/C scoring.

#### Scenario: Dataset freeze succeeds
- **WHEN** the selected set and all source/config/run hashes validate
- **THEN** Commit B contains only the three canonical dataset files; the manifest records `task_count=128`, `negative_labeled_task_count=96`, `family_count=128`, `human_author_count=0`, `human_reviewer_count=0`, exact three-way agreement counts, requested/returned model identities, reasoning efforts, run/thread IDs, prompt/schema hashes, retry records, contamination evidence, selection lineage, `model_scores_observed=false`, and `evaluation_started=false`

#### Scenario: Raw Agent traces contain hidden reasoning or runtime details
- **WHEN** Commit B documents are built
- **THEN** raw traces remain outside Git and only final task prompts, labels, sanitized summaries, and tamper-evident hashes are committed

#### Scenario: Post-freeze mutation is attempted
- **WHEN** any process attempts to change tasks, labels, reviews, gate, model, query/skill representation, checkpoint, selected rows, or Agent lineage after Commit B
- **THEN** the evaluation refuses to start

### Requirement: Exactly one terminal blind-v2 attempt is permitted
The system SHALL run only `router-v2-v4-final-blind-v2-001/attempt-1` from a fresh clean Commit B worktree after revalidating every Commit A-agent/Commit B hash, count, smoke receipt, namespace, marker, and worktree condition. Caller-supplied alternate task, model, hash, commit, evaluator, token, or output-root authorities SHALL NOT be accepted.

#### Scenario: Attempt starts
- **WHEN** all preflight checks pass and the output namespace does not exist
- **THEN** an exclusive started marker is written before inference and the attempt is irreversibly consumed

#### Scenario: Attempt fails after start
- **WHEN** any exception or infrastructure failure occurs after the started marker
- **THEN** started, terminal, and failure artifacts are retained, no retry or replacement namespace is created, and the conclusion is `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE`

#### Scenario: Ranking and latency match pilot-002
- **WHEN** any task is routed
- **THEN** only Arm A and Arm C seeds `7170`, `7171`, and `7172` participate, one untimed per-query warm-up occurs immediately before one timed pass, and cosine scores are quantized to eight decimals with `ROUND_HALF_EVEN` before deterministic skill-ID tie breaking

### Requirement: Metrics and statistics are raw-count-first and preregistered
The system SHALL report per Arm/seed Recall@1 and Recall@5 raw counts over 128, MRR, NDCG@5, Negative Hit@1 and @5 raw counts over 96, first-negative rank, p50/p95 latency, per-task gold/negative ranks, paired wins/losses/ties, and per-gold, per-negative-target, per-family, and failure slices.

#### Scenario: Aggregate analysis is produced
- **WHEN** all seed results complete
- **THEN** the system reports mean, sample standard deviation, each Arm C minus Arm A delta, pooled repeated raw counts with a non-independence warning, exact paired McNemar tests for Recall@1 and Negative Hit@5, and 10,000-resample paired bootstrap 95% intervals with seed `7170` for MRR, NDCG@5, and NHR@5 deltas

#### Scenario: Statistical uncertainty conflicts with gate direction
- **WHEN** a confidence interval or p-value is inconclusive
- **THEN** the system reports that uncertainty without adding, removing, or changing any gate

### Requirement: The unchanged pilot-002 gate is applied mechanically and always keeps baseline
The system SHALL require mean and per-seed Recall@5 delta `>= 0`, mean and per-seed MRR/NDCG@5 delta `>= -0.01`, mean NHR@5 delta `<= -0.05`, every-seed NHR@5 delta `<= 0`, and mean/every-seed p95 latency ratio `<= 1.20`. Every terminal workflow state—including dataset insufficiency, protocol invalidation, and infrastructure failure before or after the formal marker—SHALL set `router_decision=KEEP_BASELINE`, `production_ready=false`, `release_authorized=false`, and `default_router_unchanged=true`.

#### Scenario: Every gate passes
- **WHEN** all mean and every-seed thresholds pass
- **THEN** `research_conclusion` is `AGENT_BLIND_V2_GATES_PASSED` while production, release, and router promotion remain unauthorized

#### Scenario: Any gate fails
- **WHEN** one or more preregistered thresholds fail
- **THEN** `research_conclusion` is `AGENT_BLIND_V2_GATES_NOT_PASSED`, the failed gates are enumerated, and no unsupported regression claim is inferred

### Requirement: Final artifacts bind complete Agent and evaluation lineage
The system SHALL write preregistration, blind-v2 manifest, review summary, started/terminal markers, per-seed, aggregate, paired, statistics, failure slices, evaluation summary, result report, and lineage manifest under the unique final namespace.

#### Scenario: Lineage is sealed
- **WHEN** the terminal result is written
- **THEN** the lineage manifest binds historical and superseding Commit A identities, Commit B, evaluator commit, Agent configuration/prompt/schema/run hashes, staged source-ledger hashes, contamination and selection evidence, model files, frozen dataset, skill index, query contract, gate, attempt token, exact started marker, every non-self output artifact hash, and its own canonical self-hash

#### Scenario: Old artifacts are compared after completion
- **WHEN** validation recomputes repository and cache authority
- **THEN** pilot-001, pilot-002, Phase 16, training artifacts, model files, checkpoints, thresholds, and seeds show zero change

### Requirement: Public wording discloses Agent construction and limits the claim
The system SHALL update `README.md`, `README_EN.md`, `docs/resume.md`, and `docs/interview-project-overview.html` only after a terminal result and SHALL use raw counts, exact Agent configurations, unanimous-review status, same-provider limitation, gate outcome, and unchanged-default language.

#### Scenario: Gates pass
- **WHEN** every preregistered gate passes
- **THEN** public wording may state that Router V2 met the preregistered gates on a 128-task Agent-generated set accepted by two role-isolated OpenAI reviewers with unanimous labels, but MUST NOT call it human-reviewed, statistically independent, real-world human-task proof, SOTA, production-ready, release-eligible, or promotion evidence

#### Scenario: Gates do not pass
- **WHEN** any gate fails
- **THEN** public wording states that the preregistered gates were not all met on the Agent-constructed set and that the baseline remains unchanged, without claiming degradation unless the reported statistics directly support it

#### Scenario: Dataset construction terminates before evaluation
- **WHEN** the state is dataset-insufficient, protocol-invalid, or pre-attempt infrastructure-inconclusive
- **THEN** public result surfaces remain unchanged and the workflow reports only the bounded terminal reason

### Requirement: Prohibited actions remain absent
The system MUST NOT use a human author/reviewer, add an adjudicator, train, optimize, mine, relabel, tune, change thresholds/gates/seeds, select a best seed, delete hard tasks or failure artifacts, create a later attempt or blind set, modify the default router, merge, tag, release, deploy, or archive.

#### Scenario: Workflow ends in any terminal state
- **WHEN** the workflow ends in dataset-insufficient, protocol-invalid, infrastructure-inconclusive, gates-passed, or gates-not-passed state
- **THEN** the final report enumerates every prohibited action as an explicit non-action and records `human_author_count=0` and `human_reviewer_count=0`
