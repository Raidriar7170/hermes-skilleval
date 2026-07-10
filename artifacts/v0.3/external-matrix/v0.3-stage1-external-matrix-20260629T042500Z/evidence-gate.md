# Hermes SkillEval v0.3 Evidence Gate

- Benchmark Validity Gate: REVIEW_REQUIRED
- Router Promotion Gate: KEEP_BASELINE
- Invalid evidence blocks promotion: False
- Blocking failures: 0
- Review or unavailable fields: 1

## Field Markers
- external_routing: PRESENT
- live_agent: UNAVAILABLE - live-agent plan/report paths were not provided

## Checks
- PASS external.plan_load: JSON artifact loaded
- PASS external.report_load: JSON artifact loaded
- PASS external.plan_schema: external.plan_schema matches v0.3.skillrouter-matrix-plan.v1
- PASS external.report_schema: external.report_schema matches v0.3.skillrouter-matrix-report.v1
- PASS external.frozen_plan: external frozen plan is internally valid
- PASS external.input_hashes: external frozen data and prediction hashes match the plan
- PASS external.report_plan_path: report points at the validated frozen plan
- PASS external.official_metrics_present: official SkillRouter metrics are present
- PASS external.report_completeness: external official report covers exactly the frozen configs and tiers
- PASS external.hermes_diagnostics_separate: Hermes diagnostics are present separately from official metrics
- UNAVAILABLE live_agent.available: live-agent evidence was not provided
