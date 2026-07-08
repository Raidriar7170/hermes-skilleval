## ADDED Requirements

### Requirement: Validate v0.3 evidence packets

The system SHALL validate v0.3 external-routing and live-agent evidence artifacts without running new models, training, tuning, live-agent benchmarks, or release promotion.

#### Scenario: Validity gate emits only allowed statuses

- **WHEN** the evidence validator writes a report
- **THEN** the Benchmark Validity Gate status MUST be one of `VALID_EVIDENCE`, `INVALID_EVIDENCE`, or `REVIEW_REQUIRED`
- **AND** `UNAVAILABLE` MUST appear only as a field-level marker with a reason

#### Scenario: Frozen evidence fails closed

- **WHEN** a provided frozen plan, digest, source hash, derived hash, scorer report, matrix report, live-agent report, or trace is missing, malformed, contaminated, or inconsistent
- **THEN** the validator MUST mark the evidence `INVALID_EVIDENCE` or `REVIEW_REQUIRED` with explicit check records

### Requirement: Keep promotion separate and conservative

The system SHALL keep router promotion decisions separate from evidence validity.

#### Scenario: Invalid validity blocks promotion

- **WHEN** Benchmark Validity Gate status is `INVALID_EVIDENCE`
- **THEN** Router Promotion Gate MUST emit `KEEP_BASELINE`
- **AND** it MUST record that promotion is blocked by invalid evidence

#### Scenario: Default promotion is baseline

- **WHEN** evidence is valid or reviewable but no preregistered promotion approval artifact exists
- **THEN** Router Promotion Gate MUST emit `KEEP_BASELINE`

### Requirement: Report external and live-agent evidence separately

The system SHALL summarize external routing evidence and live-agent evidence in distinct report sections.

#### Scenario: External metrics are namespaced

- **WHEN** a SkillRouter external matrix report is supplied
- **THEN** the validator MUST report official routing metrics separately from Hermes diagnostics and overlap caveats

#### Scenario: Frozen external data-root provenance is accepted when local data is unmaterialized

- **WHEN** a SkillRouter frozen plan references a local external `data_root` that is not materialized in the repository
- **AND** the frozen plan contains PASS validation and complete adapter provenance fingerprints
- **THEN** the validator MUST accept the frozen provenance as the external input contract without requiring the 402MB input directory to be committed
- **AND** committed routed prediction files MUST still be rehashed against the frozen plan
- **AND** this MUST NOT imply router promotion or a performance claim

#### Scenario: Live-agent verifier outcomes are namespaced

- **WHEN** a SkillsBench live-agent matrix report is supplied
- **THEN** the validator MUST report verifier pass/fail, no-skill/routed/oracle outcomes, oracle gap, routed-vs-no-skill delta, timeout/process errors, skill-use evidence, and per-task regressions separately

#### Scenario: Stage 2 real Codex execution schema is consumable

- **WHEN** a frozen Stage 2 pilot plan and full Stage 2 real Codex execution artifact are supplied as live-agent evidence
- **THEN** the validator MUST adapt the Stage 2 schema into the live-agent evidence checks without rerunning Codex or Stage 2
- **AND** deterministic verifier output MUST remain the only task success source
- **AND** process exit code and LLM judge MUST NOT become task success sources
- **AND** router promotion MUST remain governed by the existing conservative promotion gate
