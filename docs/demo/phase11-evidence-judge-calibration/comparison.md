# Hermes SkillEval Router Comparison

Note: Phase 11 judge proxy metrics reuse the router comparison table for
dashboard compatibility. Recall and Negative fields in this artifact are
derived from judge pass/fail outcomes, not from original Phase 9 or Phase 10
router gold/negative labels. Use `judge-summary.json` for authoritative
`judge_score`, `evidence_score`, and `judge_pass_rate` values.

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| judge-agent-loop-hybrid | 12 | 0.750 | 0.750 | 0.750 | 0.750 | 0.750 | 0.750 | 0.000 | 1.000 | 1.000 | 0.000 | 0.750 | 0.000 | 0.000 |
| judge-agent-loop-no-skill-hybrid | 12 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 |
| judge-agent-loop-oracle-skill-hybrid | 12 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.267 | 0.000 | 1.000 | 0.000 | 0.000 |
