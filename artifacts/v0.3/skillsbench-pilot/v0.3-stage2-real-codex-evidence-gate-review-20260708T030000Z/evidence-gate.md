# Hermes SkillEval v0.3 Evidence Gate

- Benchmark Validity Gate: INVALID_EVIDENCE
- Router Promotion Gate: KEEP_BASELINE
- Invalid evidence blocks promotion: True
- Blocking failures: 12
- Review or unavailable fields: 1

## Field Markers
- external_routing: PRESENT
- live_agent: PRESENT

## Checks
- PASS external.plan_load: JSON artifact loaded
- PASS external.report_load: JSON artifact loaded
- PASS external.plan_schema: external.plan_schema matches v0.3.skillrouter-matrix-plan.v1
- PASS external.report_schema: external.report_schema matches v0.3.skillrouter-matrix-report.v1
- PASS external.frozen_plan: external frozen plan is internally valid
- FAIL external.input_hashes: external validation failed
- PASS external.report_plan_path: report points at the validated frozen plan
- PASS external.official_metrics_present: official SkillRouter metrics are present
- PASS external.report_completeness: external official report covers exactly the frozen configs and tiers
- PASS external.hermes_diagnostics_separate: Hermes diagnostics are present separately from official metrics
- FAIL live_agent.plan_digest: missing plan digest sidecar: stage2-pilot-plan.frozen.json.sha256
- PASS live_agent.plan_load: JSON artifact loaded
- PASS live_agent.report_load: JSON artifact loaded
- FAIL live_agent.plan_schema: live_agent.plan_schema expected v0.3.skillsbench-live-plan.v1, got v0.3.stage2-pilot-plan-freeze.v1
- FAIL live_agent.report_schema: live_agent.report_schema expected v0.3.skillsbench-live-matrix-report.v1, got v0.3.stage2-real-codex-12-run-matrix-report.v1
- FAIL live_agent.input_hashes: 'adapter_provenance'
- FAIL live_agent.derived_hashes: missing derived field hashes
- FAIL live_agent.report_plan_path: report plan_path does not match the validated plan
- FAIL live_agent.matrix_completeness: live-agent matrix or runs are malformed
- PASS live_agent.prompt_hash_equality: all conditions use the same prompt hash per task
- PASS live_agent.oracle_qualification: oracle qualification passed for every selected live task
- FAIL live_agent.verifier_evidence: verifier evidence is incomplete or not the success source
- FAIL live_agent.no_skill_leakage: no-skill condition shows benchmark skill leakage
- REVIEW live_agent.global_capability_inventory: global capability inventory is missing
- FAIL live_agent.trace_completeness: live-agent trace files are missing, incomplete, or inconsistent with report rows
- FAIL live_agent.overlap_status: overlap report decision is missing or unsupported
- PASS live_agent.secret_redaction: live-agent report and traces do not contain obvious secret tokens
- PASS live_agent.timeout_process_errors: no live-agent timeout or process errors were reported
- PASS live_agent.per_task_regressions: no routed-skill per-task regressions versus no-skill were reported
