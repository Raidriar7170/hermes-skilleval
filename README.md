# Hermes SkillEval

Hermes SkillEval is an offline CLI harness for evaluating skill routing in Hermes-style agent skill libraries.

The MVP indexes `skills/**/SKILL.md`, loads labeled benchmark tasks, compares routers, and writes reproducible JSONL and Markdown reports. It does not require Hermes Agent, network access, or an LLM API key.

## Quickstart

Install editable: `python -m pip install -e ".[dev]"`

Index: `skilleval index --skills-path /path/to/hermes/skills --output index/skills.json`

Eval: `skilleval eval --index index/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir runs/latest`

Report: `skilleval report --runs runs/latest`

Tests: `pytest -v`

## Metrics

Reports include Recall@1, Recall@3, Recall@5, Precision@5, MRR, NDCG@5, Negative Hit Rate, latency, top selected skills, and failure cases.

## Scope

This first version evaluates skill selection only. Real Hermes execution, LLM judges, automatic skill patching, and web dashboards are planned future extensions.
