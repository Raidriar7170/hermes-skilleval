# Hermes SkillEval v0.3 Evidence Gate

- Benchmark Validity Gate: INVALID_EVIDENCE
- Router Promotion Gate: KEEP_BASELINE
- Invalid evidence blocks promotion: True
- Blocking failures: 1
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
- PASS live_agent.plan_load: JSON artifact loaded
- PASS live_agent.report_load: JSON artifact loaded
- PASS live_agent.stage2_schema_adapter: Stage 2 real Codex execution schema was adapted for live-agent evidence checks
- PASS live_agent.matrix_completeness: live-agent report contains exactly the frozen matrix runs
- PASS live_agent.prompt_hash_equality: all conditions use the same prompt hash per task
- PASS live_agent.oracle_qualification: oracle qualification passed for every selected live task
- PASS live_agent.verifier_evidence: deterministic verifier records are complete and source task success
- PASS live_agent.no_skill_leakage: no-skill condition mounted no benchmark skills
- PASS live_agent.global_capability_inventory: global capability inventory has no detected user/admin/repo leakage
- PASS live_agent.trace_completeness: all live-agent runs have complete trace files
- REVIEW live_agent.overlap_status: overlap report requires caveated generalization claims
- PASS live_agent.secret_redaction: live-agent report and traces do not contain obvious secret tokens
- PASS live_agent.timeout_process_errors: no live-agent timeout or process errors were reported
- PASS live_agent.per_task_regressions: no routed-skill per-task regressions versus no-skill were reported
