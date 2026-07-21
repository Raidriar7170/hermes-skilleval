# Router V2 Final Blind-v2 Agent-only Protocol

## Active research question

Do the unchanged Router V2 Arm C checkpoints meet the unchanged pilot-002 gate once on a preregistered 128-task Agent-constructed set accepted by two role-isolated reviewers with unanimous labels?

This is one preregistered Agent-constructed evaluation, not a training or model-development phase. All conclusions are bounded to this 128-task Agent-generated set; same-provider role isolation is not statistical independence and is not evidence of human-task generalization.

Run 003 terminal truth:

- `research_conclusion=AGENT_BLIND_V2_DATASET_INSUFFICIENT`
- `router_decision=KEEP_BASELINE`
- `human_author_count=0`
- `human_reviewer_count=0`
- `model_scores_observed=false`
- `evaluation_started=false`

## Run 003 Agent construction closeout (executed; stopped before Commit B)

Run 001 remains immutable at
`artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001/candidate-generation-terminal.json`
with SHA-256
`74b8e9fb01e008ee40c1f38c65c73a9fde371c615e4689f847ab88887cefa6ea`.
Run 002 has no standalone terminal JSON. Its terminal evidence is the exact
private five-file canary bundle bound to Git commit
`8a34995f85954777b1130c4be8c94a2e5e3e950b`; the canonical bundle SHA-256 is
`ca1c9c4b6b908d62442dd64f2a9b1b9891182662a29e1824c91c15b7416971b5`.
No Run 001 or Run 002 candidate response is reusable.

The Run 002 terminal Git commit is predecessor evidence only; it is not the
Run 003 Commit A. Run 003 executed from Commit A
`2d326d95eeb6b545295d55ac937cfbf902a0d956`, whose sole parent is the Run 002
terminal commit. No Run 001 or Run 002 candidate was reused.

The executed authority ID is
`router-v2-v4-successor-blind-v2-003`, with replacement reason
`ALLOW_VALIDATED_TRANSIENT_TRANSPORT_DIAGNOSTICS`. Its private root,
`run003-authority-manifest.json`, dataset destination
`data/router-v2-blind-v2-successor-003/`, and evaluation namespace
`artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-003/` are distinct
from both predecessors. Construction, pack validation, freeze, model-smoke, and
evaluation require the explicit `run003` selector.

Run 003 alone uses event policy
`router-v2-run003-validated-transient-transport-diagnostics-v1`. An event with
exact fields `{type,message}` may be recorded as a non-fatal diagnostic only
when its message is classified as a known transient TLS disconnect, transport
timeout, connection reset, stream disconnect, or transport retry and the same
invocation still proves one unique thread, one completed turn, exit code zero,
zero tools, zero descendants, one final Agent message identical to the response
file, and a schema-valid response. Authentication, application, business,
unknown, extra-field, incomplete, multiple-final, tool, descendant, nonzero-exit,
and invalid-response cases remain fail-closed. Diagnostic count, sorted unique
types, and observed status are carried through the invocation envelope, role and
top-level construction metadata, pack replay, review summary, and dataset
manifest. A validated diagnostic is not a retry and does not relax the existing
one-byte-identical-retry rule for failures with no valid response.

Authority replay preserves `run001_candidates_reused=false`,
`run002_candidates_reused=false`, `run001_model_scores_observed=false`,
`run002_model_scores_observed=false`, and Run 003
`model_scores_observed=false`. Diagnostic counts never incremented the
controller retry count.

The synthetic canary completed one successful Generator invocation, returned
16 candidates, recorded zero diagnostics, wrote no formal candidate data, and
loaded no Router model. Formal round 1 then issued 16 requests and produced 256
candidates; the single allowed supplement issued another 16 requests and
produced 256 candidates. The fixed configurations were Generator
`gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B
`gpt-5.6-luna/max`. Controller retry count was zero and no fallback was used.

Across all 512 candidates, contamination filtering recorded
`398 PASS / 114 REJECT`. Reviewer A processed all 398 clean candidates: 397 were valid
`ACCEPT` responses and one invocation was invalid as
`FORMAL_ISOLATION_BLOCKED`. Reviewer B also processed all 398: 397 were valid
`ACCEPT` responses and one invocation was invalid as
`FORMAL_OUTPUT_BLOCKED / SCHEMA_INVALID`. Three-way gold agreement was 396;
exact three-way gold+negative/none agreement was 99. Deterministic deduplication
and quota selection retained 87 tasks—85 negative-labeled and two
positive-only—across 87 distinct semantic families. Twelve otherwise eligible
candidates were not selected.

| Candidate outcome | Count |
|---|---:|
| selected | 87 |
| not_selected | 12 |
| rejected_contamination | 114 |
| rejected_invocation | 2 |
| rejected_review | 297 |
| total | 512 |

The remaining negative / positive-only deficits were:

| Gold skill | Negative deficit | Positive-only deficit |
|---|---:|---:|
| accessibility | 0 | 2 |
| apply-patch | 2 | 2 |
| browser-smoke | 3 | 2 |
| evidence-backed | 0 | 2 |
| form-interaction | 0 | 2 |
| plan-mode | 0 | 2 |
| slash-command | 1 | 2 |
| subagent-worker | 5 | 2 |
| systematic-debugging | 0 | 2 |
| task-tool-delegation | 0 | 2 |
| TDD | 0 | 2 |
| worktrees | 0 | 2 |
| verification | 0 | 2 |
| visual-regression | 0 | 2 |
| workspace-git | 0 | 2 |

`mcp-tool-routing` had no deficit. The deficits total 11 negative tasks and 30
positive-only tasks, so the frozen `128 tasks / 96 negatives / 128 families`
contract could not be satisfied. The workflow therefore terminalized exactly
as preregistered at `AGENT_BLIND_V2_DATASET_INSUFFICIENT / KEEP_BASELINE`; it
did not lower quotas or add another generation round.

Construction metadata recorded 27 classified transport diagnostics: Generator
5, Reviewer A 9, and Reviewer B 13. Their only types were
`TEMPORARY_TLS_DISCONNECT` and `TEMPORARY_TRANSPORT_TIMEOUT`. They satisfied the
Run 003 diagnostic policy and did not become retries.

No Commit B exists. No Arm A/C model was loaded or scored; no formal attempt
marker, per-seed result, aggregate/statistical result, or gate metric exists.
`production_ready=false`, `release_authorized=false`, and
`default_router_unchanged=true` remain fixed. This is an Agent-only dataset
construction terminal, not human-reviewed evidence, a public benchmark result,
a SOTA claim, production readiness, or router promotion.

## Stage 0 Agent-runtime requalification (qualified; Commit A2 pending)

The prior configuration smoke is immutable failed audit history. Commit A-agent
`50069a124a8d129e11926e78d1bcc2388bc91a22` terminalized in commit
`c208ddde330b408e571df0e315ee3f688bff32e8`; the canonical v2 terminal artifact
was finalized by `c90595862089ab8d201077fdedf8a1d083ff4498`.
It proves `failure_stage=agent_config_smoke`, zero candidates, no Commit B, no
Arm A/C load, no model score, no formal evaluation, and no attempt marker. The
old v1 smoke receipt is not a qualification receipt and remains
`FAILED_AUDIT_HISTORY_ONLY`.

The repository preregistration now records
`STAGE0_QUALIFIED_COMMIT_A2_PENDING`, binds the qualified receipt self-hash,
and records exactly three observed top-level invocations. The separately
authorized Stage 0 Goal made exactly the three frozen calls and wrote one
exclusive, hash-bound qualified receipt. Those roles must not be invoked again.
Separate Commit A2 authorization now permits preparation and creation of that
administrative successor only. Candidate generation, model loading/scoring,
and formal evaluation remain unauthorized until Commit A2 exists as clean
authority.

- Prior terminal artifact SHA-256: `b83aea9ea8fb1bb6bfd3baa58ac23347765bc9bda48a08c20185088d45fe193e`
- Stage 0 contract SHA-256: `140175c56684ed35956975511384cef51b3ec5ff527869c63507e8e710366739`
- Stage 0 receipt self-hash SHA-256: `9009d03fe349efcf60e4f58b0a0b63a9fcaf2a78a04b7d4d838486212bbb9118`
- Scientific contract SHA-256: `5865263ab3e63aad375a16259d5ff4391d48b011e104b8a0fb3c96b476262cc5`
- Scientific projection SHA-256: `58a5d40fdf3b966dc3e16c81321bafe4391ffc0bb9910d8f11154b2aa5d9e866`

| Role | Requested alias | Reasoning | Timeout | Frozen nonce |
|---|---|---|---:|---|
| Generator | `gpt-5.6-sol` | `max` | 1800 | `generator-7170-4f87d78d` |
| Reviewer A | `gpt-5.6-sol` | `ultra` | 900 | `reviewer-a-7170-b8ce599a` |
| Reviewer B | `gpt-5.6-luna` | `max` | 900 | `reviewer-b-7170-30e5fcef` |

The Stage 0 host made exactly one fresh, top-level,
`fork_context=false` dummy call per role, with empty history, zero imported
memory, zero tools, zero descendants, one response, and no retry or fallback.
Each response must be one UTF-8 JSON object containing exactly `protocol`,
`role`, `nonce`, and `status=READY`; duplicate keys, extra or missing fields,
surrounding prose, invalid UTF-8, or semantic mismatch fail closed. The host
ledger preserves raw response bytes as base64 and binds the full top-level and
per-invocation field lists in the Stage 0 contract hash.

The frozen logical ledger root remains
`/tmp/hermes-router-v2-blind-v2-stage0`. A platform-owned `/tmp` entry may
resolve to a real sticky temporary directory (as on macOS), but every component
below `/tmp` remains non-symlinked. This narrow alias rule does not permit
relocation to `/private/tmp`, `$TMPDIR`, a home directory, or another
fallback. The Stage 0 and receipt directories are `0700`; the ledger and every
terminal receipt are regular `0600` files. Receipt creation is hash-bound and
exclusive, and validation rejects any symlink, non-regular file, parent mode
other than `0700`, or file mode other than `0600` before reading bytes.
Outside-repository checks remain mandatory.

Requested model alias and reasoning effort are attested by the host invocation
envelope, not by Agent self-report. `provider_returned_model` is nullable;
absence is recorded as `INTERFACE_UNAVAILABLE`. Host-envelope qualification
does not independently prove backend alias resolution, and that limitation must
remain disclosed.

The only Stage 0 terminal states are
`AGENT_RUNTIME_STAGE0_QUALIFIED`,
`AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE`,
`AGENT_RUNTIME_STAGE0_CANARY_MISMATCH`,
`AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION`,
`AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE`,
`AGENT_RUNTIME_STAGE0_TRANSPORT_FAILURE`, and
`AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT`. Every state keeps `KEEP_BASELINE`,
`production_ready=false`, `release_authorized=false`, and the default router
unchanged. Qualification plus the separately received authorization permits
only preparation and creation of Commit A2; it does not authorize candidate
generation, model access, scoring, or formal evaluation.

The separately authorized Commit A2, after this qualified receipt and a fresh
zero-exposure audit, must be one direct child of
`b756a411cc8910999ae1c05d4b5c7a05868302ad`, use the exact preregistered
changed-file boundary, and record
`supersession_reason=PRE_DATA_HOST_ATTESTATION_CONTRACT_REPAIR`. It is a
pre-data contract repair—not attempt-2, `blind-v2-002`, blind-v3, a replacement
dataset, or a repeated formal evaluation. All existing generation, review,
freeze, model-smoke, and evaluation commands remain blocked until that authority
exists.

## Frozen repository and evaluation authority

- Origin authority: `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552`
- Task 8 pre-edit HEAD: `0998b814e82b4da164a54d0a6ce219573f037994`
- Canonical skill count: `16`
- Evaluator contract SHA-256: `575ec2c596a2cd2bfdd33ae59209adcd815e89c24ab7b254ede2c9387a992a56`
- Evaluator source aggregate SHA-256: `b76c3de0f82b5ffbc13c2e15eb4ec310ff2657bad9d96b0cfc3b7bc107c225f9`
- Frozen-input aggregate SHA-256: `dd2ea7dd0fe1675cb87bc6ece6cea8f330afb98c7cb52cd69676ca259e275056`
- Gate semantic SHA-256: `19a53521277f914393fcb815e9c35a1e2e6bc549b0db49027d03e1d6cd875bba`
- Skill-index semantic SHA-256: `23a3123bd2247f1d209b616212d3118db5851f3a8a3891493d265fc7fa46a036`
- Query-contract semantic SHA-256: `4e1ea3f5eb074939abccc1e8198286e55313b385545fc1c4f45e0b47bd11b2a5`
- Skill-representation semantic SHA-256: `5959ad6e5c9b700cf17ccd0ccede02c3777c6e9d7c13da4a933dbae40e07faa3`
- Phase 16 binding aggregate SHA-256: `e6cbc0d7aeb9f04928b635892409fe21c70a038439b875015a25ffce921fd39a`
- Protected semantic commitment SHA-256: `0e7ab288035d274e3cbee8cc5f15c0a74b5e080d6fa7b6aea5377fd5dc43122a`

Protected Task 8 baseline subtrees:

| Subtree | Canonical SHA-256 |
|---|---|
| `arm_c_checkpoints` | `09a462fe6d888bffb75ffed7187bfe397e17224227d4c2126c82eb909e95d2ce` |
| `base_model` | `9c8c287edecec1d3db119afbad9468a6fe71b5c3c591e3068b9a4a3275c6cc2d` |
| `frozen_inputs` | `dd2ea7dd0fe1675cb87bc6ece6cea8f330afb98c7cb52cd69676ca259e275056` |
| `gate` | `19a53521277f914393fcb815e9c35a1e2e6bc549b0db49027d03e1d6cd875bba` |
| `old_phase16_prompt_files` | `e6cbc0d7aeb9f04928b635892409fe21c70a038439b875015a25ffce921fd39a` |
| `pilot_002_gate_artifact` | `3a2641bae204676574dc2c58d15198bbd601ce8ec82a3deeca9aedb1c71cfb9a` |
| `query_contract` | `4e1ea3f5eb074939abccc1e8198286e55313b385545fc1c4f45e0b47bd11b2a5` |
| `skill_index` | `61349bc19f92705aa0ba0c410ffc79cee52103823a20250bd9908fa248b813f3` |
| `skill_representation_builder` | `5959ad6e5c9b700cf17ccd0ccede02c3777c6e9d7c13da4a933dbae40e07faa3` |

## Generator authority

Configuration: model `gpt-5.6-sol`, reasoning effort `max`, timeout `1800` seconds.

Canonical system prompt (verbatim):

```text
You are the Generator for a preregistered Router V2 blind evaluation. Create natural English user requests for exactly one primary canonical skill. Do not mention skill IDs, skill names, gold labels, negative labels, benchmarks, routers, training, pilot data, Phase 16, Arm A, Arm C, or model behavior. For a negative-labeled candidate, choose one plausible but insufficient canonical negative skill. Use only the supplied skill definitions and quota. Do not use external memory or prior conversation. Return only JSON matching the supplied schema.
```

System-prompt SHA-256: `e9b9107f4f520d7674e56ef2ae2fca169b1eff44cc3ac6f0b2a389af8fd9f591`

Task 8 human-readable response schema (verbatim):

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

Human-readable schema SHA-256: `0be38cdf009aecf69075810bed3f2ac059df157d1a9d2a7635f472155d923a3e`

Enforced response JSON Schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "candidates": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "candidate_index": {
            "minimum": 0,
            "type": "integer"
          },
          "language": {
            "const": "en"
          },
          "prompt_text": {
            "minLength": 1,
            "pattern": "\\S",
            "type": "string"
          },
          "proposed_gold_skill_id": {
            "minLength": 1,
            "pattern": "\\S",
            "type": "string"
          },
          "proposed_negative_skill_id": {
            "pattern": "\\S",
            "type": [
              "string",
              "null"
            ]
          },
          "rationale": {
            "minLength": 1,
            "pattern": "\\S",
            "type": "string"
          },
          "semantic_family_id": {
            "minLength": 1,
            "pattern": "\\S",
            "type": "string"
          }
        },
        "required": [
          "candidate_index",
          "prompt_text",
          "semantic_family_id",
          "proposed_gold_skill_id",
          "proposed_negative_skill_id",
          "language",
          "rationale"
        ],
        "type": "object"
      },
      "type": "array"
    }
  },
  "required": [
    "candidates"
  ],
  "type": "object"
}
```

Response JSON Schema SHA-256: `24e63da6d922bc7dd9af8e8eed0b64f44850fcbda70898b7784d5e89260f304e`

Request schema authority:

```json
{
  "canonical_skill_fields": [
    "id",
    "name",
    "category",
    "description",
    "trigger_terms",
    "body"
  ],
  "input_fields": [
    "canonical_skills",
    "rules",
    "quota"
  ],
  "quota_fields": [
    "gold_skill_id",
    "negative_quota",
    "positive_only_quota",
    "round_number"
  ],
  "schema_version": "router-v2-blind-v2-generation-request-v1",
  "top_level_fields": [
    "schema_version",
    "role",
    "model",
    "reasoning_effort",
    "timeout_seconds",
    "system_prompt",
    "response_schema",
    "input",
    "request_sha256"
  ]
}
```

Request schema SHA-256: `5fe549b241c0a2c76beb1e47603878d54524c7a126e37d0917d683089608445f`

Each round-1 skill request returns exactly 16 candidate objects: 12 negative-labeled and four positive-only proposals. The Generator does not assign candidate IDs.

Controller candidate-ID rule: `first 24 hex characters of sha256(f"{round_number}:{skill_id}:{candidate_index}:{response_sha256}")`
Candidate-ID rule SHA-256: `2d7de27ccf9ba219cb988790afa36a461e15bd331955f075d08d7dc69cf2e526`

## Reviewer A authority

Configuration: model `gpt-5.6-sol`, reasoning effort `ultra`, timeout `900` seconds.

Canonical system prompt (verbatim):

```text
You are a role-isolated reviewer for one preregistered Router V2 blind candidate. Use only the supplied task text, canonical skill definitions, and rubric. Independently decide the single primary gold skill and one plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural wording, label leakage, invalid negatives, and tasks with more than one equally primary skill. Do not use external memory, prior conversation, quotas, other reviews, generator labels, Router models, or model results. Return only JSON matching the supplied schema.
```

System-prompt SHA-256: `d28bff9b9ede1d33f39a7520e6b168dae166e38a53e4067c626a23a9f4437ca2`

Task 8 human-readable response schema (verbatim):

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

Human-readable schema SHA-256: `a2c9a5679e2c7e8b20ec73782b73689fc135856fd16793f19f300a5b265f8b90`

Enforced response JSON Schema:

```json
{
  "additionalProperties": false,
  "allOf": [
    {
      "else": {
        "properties": {
          "negative_confusable": {
            "type": "boolean"
          }
        }
      },
      "if": {
        "properties": {
          "reviewed_negative_skill_id": {
            "type": "null"
          }
        },
        "required": [
          "reviewed_negative_skill_id"
        ]
      },
      "then": {
        "properties": {
          "negative_confusable": {
            "type": "null"
          }
        }
      }
    }
  ],
  "oneOf": [
    {
      "if": {
        "properties": {
          "reviewed_negative_skill_id": {
            "type": "string"
          }
        },
        "required": [
          "reviewed_negative_skill_id"
        ]
      },
      "properties": {
        "decision": {
          "const": "ACCEPT"
        },
        "natural": {
          "const": true
        },
        "no_label_leakage": {
          "const": true
        },
        "single_primary_skill": {
          "const": true
        }
      },
      "then": {
        "properties": {
          "negative_confusable": {
            "const": true
          }
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_AMBIGUOUS"
        },
        "single_primary_skill": {
          "const": false
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_NOT_CONFUSABLE"
        },
        "negative_confusable": {
          "const": false
        },
        "reviewed_negative_skill_id": {
          "pattern": "\\S",
          "type": "string"
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_UNNATURAL"
        },
        "natural": {
          "const": false
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_LABEL_LEAKAGE"
        },
        "no_label_leakage": {
          "const": false
        }
      }
    }
  ],
  "properties": {
    "confidence": {
      "enum": [
        "LOW",
        "MEDIUM",
        "HIGH"
      ]
    },
    "decision": {
      "enum": [
        "ACCEPT",
        "REJECT_AMBIGUOUS",
        "REJECT_NOT_CONFUSABLE",
        "REJECT_UNNATURAL",
        "REJECT_LABEL_LEAKAGE"
      ]
    },
    "natural": {
      "type": "boolean"
    },
    "negative_confusable": {
      "type": [
        "boolean",
        "null"
      ]
    },
    "no_label_leakage": {
      "type": "boolean"
    },
    "reason": {
      "minLength": 1,
      "pattern": "\\S",
      "type": "string"
    },
    "reviewed_gold_skill_id": {
      "minLength": 1,
      "pattern": "\\S",
      "type": "string"
    },
    "reviewed_negative_skill_id": {
      "pattern": "\\S",
      "type": [
        "string",
        "null"
      ]
    },
    "single_primary_skill": {
      "type": "boolean"
    }
  },
  "required": [
    "decision",
    "reviewed_gold_skill_id",
    "reviewed_negative_skill_id",
    "natural",
    "single_primary_skill",
    "no_label_leakage",
    "negative_confusable",
    "confidence",
    "reason"
  ],
  "type": "object"
}
```

Response JSON Schema SHA-256: `14bc1d39858bf735bfd75f3055cf0761c919aaeb7b079f97e8419a05232f80cb`

Request schema authority:

```json
{
  "canonical_skill_fields": [
    "id",
    "name",
    "category",
    "description",
    "trigger_terms",
    "body"
  ],
  "input_fields": [
    "task_id",
    "prompt_text",
    "canonical_skills",
    "rubric"
  ],
  "schema_version": "router-v2-blind-v2-review-request-v1",
  "top_level_fields": [
    "schema_version",
    "role",
    "model",
    "reasoning_effort",
    "timeout_seconds",
    "system_prompt",
    "response_schema",
    "input",
    "request_sha256"
  ]
}
```

Request schema SHA-256: `00c33449e8b811029a647a71e4d7e59623e66d0132439aae97e7b70b88a1c440`

`negative_confusable` semantics: true when reviewed_negative_skill_id is non-null; null when the reviewer independently selects no negative.

Schedule: `ascending sha256("review-a:7170:" + candidate_id)`
Schedule-rule SHA-256: `f3bf04f5c9a46969c3745b56edfa39382bb025ed00ffcbaddd874cd71c3c2566`
Runtime schedule hash: `canonical_sha256(ordered_candidate_ids)`

## Reviewer B authority

Configuration: model `gpt-5.6-luna`, reasoning effort `max`, timeout `900` seconds.

Canonical system prompt (verbatim):

```text
You are a role-isolated reviewer for one preregistered Router V2 blind candidate. Use only the supplied task text, canonical skill definitions, and rubric. Independently decide the single primary gold skill and one plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural wording, label leakage, invalid negatives, and tasks with more than one equally primary skill. Do not use external memory, prior conversation, quotas, other reviews, generator labels, Router models, or model results. Return only JSON matching the supplied schema.
```

System-prompt SHA-256: `d28bff9b9ede1d33f39a7520e6b168dae166e38a53e4067c626a23a9f4437ca2`

Task 8 human-readable response schema (verbatim):

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

Human-readable schema SHA-256: `a2c9a5679e2c7e8b20ec73782b73689fc135856fd16793f19f300a5b265f8b90`

Enforced response JSON Schema:

```json
{
  "additionalProperties": false,
  "allOf": [
    {
      "else": {
        "properties": {
          "negative_confusable": {
            "type": "boolean"
          }
        }
      },
      "if": {
        "properties": {
          "reviewed_negative_skill_id": {
            "type": "null"
          }
        },
        "required": [
          "reviewed_negative_skill_id"
        ]
      },
      "then": {
        "properties": {
          "negative_confusable": {
            "type": "null"
          }
        }
      }
    }
  ],
  "oneOf": [
    {
      "if": {
        "properties": {
          "reviewed_negative_skill_id": {
            "type": "string"
          }
        },
        "required": [
          "reviewed_negative_skill_id"
        ]
      },
      "properties": {
        "decision": {
          "const": "ACCEPT"
        },
        "natural": {
          "const": true
        },
        "no_label_leakage": {
          "const": true
        },
        "single_primary_skill": {
          "const": true
        }
      },
      "then": {
        "properties": {
          "negative_confusable": {
            "const": true
          }
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_AMBIGUOUS"
        },
        "single_primary_skill": {
          "const": false
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_NOT_CONFUSABLE"
        },
        "negative_confusable": {
          "const": false
        },
        "reviewed_negative_skill_id": {
          "pattern": "\\S",
          "type": "string"
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_UNNATURAL"
        },
        "natural": {
          "const": false
        }
      }
    },
    {
      "properties": {
        "decision": {
          "const": "REJECT_LABEL_LEAKAGE"
        },
        "no_label_leakage": {
          "const": false
        }
      }
    }
  ],
  "properties": {
    "confidence": {
      "enum": [
        "LOW",
        "MEDIUM",
        "HIGH"
      ]
    },
    "decision": {
      "enum": [
        "ACCEPT",
        "REJECT_AMBIGUOUS",
        "REJECT_NOT_CONFUSABLE",
        "REJECT_UNNATURAL",
        "REJECT_LABEL_LEAKAGE"
      ]
    },
    "natural": {
      "type": "boolean"
    },
    "negative_confusable": {
      "type": [
        "boolean",
        "null"
      ]
    },
    "no_label_leakage": {
      "type": "boolean"
    },
    "reason": {
      "minLength": 1,
      "pattern": "\\S",
      "type": "string"
    },
    "reviewed_gold_skill_id": {
      "minLength": 1,
      "pattern": "\\S",
      "type": "string"
    },
    "reviewed_negative_skill_id": {
      "pattern": "\\S",
      "type": [
        "string",
        "null"
      ]
    },
    "single_primary_skill": {
      "type": "boolean"
    }
  },
  "required": [
    "decision",
    "reviewed_gold_skill_id",
    "reviewed_negative_skill_id",
    "natural",
    "single_primary_skill",
    "no_label_leakage",
    "negative_confusable",
    "confidence",
    "reason"
  ],
  "type": "object"
}
```

Response JSON Schema SHA-256: `14bc1d39858bf735bfd75f3055cf0761c919aaeb7b079f97e8419a05232f80cb`

Request schema authority:

```json
{
  "canonical_skill_fields": [
    "id",
    "name",
    "category",
    "description",
    "trigger_terms",
    "body"
  ],
  "input_fields": [
    "task_id",
    "prompt_text",
    "canonical_skills",
    "rubric"
  ],
  "schema_version": "router-v2-blind-v2-review-request-v1",
  "top_level_fields": [
    "schema_version",
    "role",
    "model",
    "reasoning_effort",
    "timeout_seconds",
    "system_prompt",
    "response_schema",
    "input",
    "request_sha256"
  ]
}
```

Request schema SHA-256: `00c33449e8b811029a647a71e4d7e59623e66d0132439aae97e7b70b88a1c440`

`negative_confusable` semantics: true when reviewed_negative_skill_id is non-null; null when the reviewer independently selects no negative.

Schedule: `ascending sha256("review-b:7171:" + candidate_id)`
Schedule-rule SHA-256: `9fc748836a9081a6f466c04487da95afaee1fb452012c84c93de8e40d96621b1`
Runtime schedule hash: `canonical_sha256(ordered_candidate_ids)`

## Isolation and transport-only retry

```json
{
  "fork_context": false,
  "fresh_session_per_invocation": true,
  "generator_external_memory_allowed": false,
  "history_message_count": 0,
  "imported_memory_count": 0,
  "reviewer_candidate_count_per_session": 1,
  "reviewer_external_memory_allowed": false,
  "unique_session_or_thread_id": true
}
```

```json
{
  "byte_identical_request_required": true,
  "condition": "recorded transport failure with no syntactically valid response bytes",
  "fallback_model_allowed": false,
  "fresh_session_required": true,
  "identical_model_alias_required": true,
  "identical_prompt_hash_required": true,
  "identical_reasoning_effort_required": true,
  "maximum_retries": 1,
  "substantive_response_retry_allowed": false
}
```

Every invocation is fresh and non-forked with empty history and no imported memory. A single retry uses a fresh session and is permitted only after a recorded transport failure with no valid response bytes. Model mismatch, refusal, invalid schema, label disagreement, or rubric rejection is substantive and receives no retry or fallback.

Formal Generator and Reviewer calls use the hash-bound
`router-v2-blind-v2-formal-agent-invocation-v2` host-envelope contract. The
requested model alias and reasoning effort in the host request are authoritative;
model or reasoning fields emitted in Agent response text are never identity
evidence. Provider-returned model metadata has exactly two legal states:
`returned_model=null` with
`provider_returned_model_status=INTERFACE_UNAVAILABLE`, or the exact requested
alias with `provider_returned_model_status=AVAILABLE`. Missing status, a
different alias, or any other combination fails closed.

Every formal invocation, including a transport-failure row, also requires
host-observed `lineage_observed=true`, `tool_call_count=0`, and
`descendant_agent_count=0`. These provider and lineage fields are preserved in
external Agent metadata, sanitized attempt/terminal records, transport-retry
records, the frozen ledger, and evaluation replay; missing or nonzero lineage at
any layer invalidates the pack or replay. Any response bytes are substantive
even when provider metadata is unavailable, so a refusal or invalid response
cannot be reclassified as transport failure to obtain a retry. The older
canonical Agent-config smoke retains its strict returned-model check only as
immutable failed audit history; it is not the authority for formal generation,
review, freeze, or evaluation.

## Generation rounds, unanimous admission, and deterministic selection

```json
{
  "maximum_generation_rounds": 2,
  "round_1": {
    "candidate_count": 256,
    "candidate_count_per_skill": 16,
    "negative_labeled_per_skill": 12,
    "positive_only_per_skill": 4,
    "request_count": 16,
    "skill_count": 16,
    "skill_schedule": "ascending canonical skill id"
  },
  "round_2": {
    "allowed": true,
    "candidate_count_rule": "twice each final stratum deficit",
    "deficit_only": true,
    "full_scan_and_dual_review_required": true,
    "maximum_round_count": 1,
    "rejection_feedback_allowed": false
  },
  "round_3_allowed": false
}
```

```json
{
  "canonical_skill_count": 16,
  "family_count": 128,
  "negative_labeled_per_gold_skill": 6,
  "negative_labeled_task_count": 96,
  "positive_only_per_gold_skill": 2,
  "task_count": 128,
  "tasks_per_gold_skill": 8
}
```

```json
{
  "confidence_used": false,
  "ordering": "ascending lexicographic selection key within each (gold_skill_id, negative_or_positive_only) stratum",
  "rationale_used": false,
  "selection_key_rule": "sha256(\"7170:\" + candidate_id)",
  "selection_key_rule_sha256": "52c1120b65fcd4f124393a66f5873023a9504824d86364858fec1458bd2f588f",
  "selection_seed": 7170
}
```

Round 1 contains 16 skill requests and exactly 256 candidates. Round 2 is optional, deficit-only, and produces exactly twice each remaining stratum deficit. Every round-2 row repeats the complete contamination scan and two fresh reviews. There is no round 3.

Admission requires both reviewers to emit `ACCEPT`, affirm every frozen rubric boolean, and exactly match the Generator and each other on gold and negative-or-null. No adjudication, majority vote, relabeling, feedback, confidence selection, or rationale selection is allowed.

## Non-voting contamination authority

- Model ID: `sentence-transformers/all-mpnet-base-v2`
- Revision: `e8c3b32edf5434bc2275fc9bab85f82640a19130`
- Exact local snapshot: `/Users/raidriar/.cache/huggingface/hub/models--sentence-transformers--all-mpnet-base-v2/snapshots/e8c3b32edf5434bc2275fc9bab85f82640a19130`
- Materialized files: `28`
- Materialized bytes: `3824846935`
- Aggregate authority SHA-256: `11a0b5bd48efbae208424572fe30f873a139d552582047201c96e3b6d85b7f1a`
- Semantic authority self-hash: `e947d4c06ad542fbdebbd5f4dcb04300b466f0f7643ae62ad800cef2b25c704a`
- Normalization: `NFKC-casefold-collapse-whitespace`
- `character_5gram_jaccard_reject_at_or_above=0.85`
- `semantic_cosine_reject_at_or_above=0.90`
- `token_5gram_jaccard_reject_at_or_above=0.80`
- Embeddings are normalized and prompt-only; Router skill representations and Arm A/C are not used.

| Snapshot-relative file | Size | SHA-256 |
|---|---:|---|
| `.gitattributes` | `1229` | `98ccb431c012ebfe976280fbd45aea4cec7409935868ccecf3954370f96732a1` |
| `1_Pooling/config.json` | `190` | `a37f83ada23e7887be6b88f4998927dbeac0038af301553c7cd5461413bf1a56` |
| `README.md` | `11612` | `89a1a9c3290fe58e76c939b578c48a14331dc7bfcaaf5a53102adb183da6f96a` |
| `config.json` | `571` | `d46a3e04ded82bba22528424480697d394eeda6a27484e08c5bb2bdf5906cfa0` |
| `config_sentence_transformers.json` | `116` | `061ca9d39661d6c6d6de5ba27f79a1cd5770ea247f8d46412a68a498dc5ac9f3` |
| `data_config.json` | `39265` | `32edcb108fc2516b920734a862ae0692bcae1c5d45d5f8d972cb0d53434a4c54` |
| `model.safetensors` | `437971872` | `78c0197b6159d92658e319bc1d72e4c73a9a03dd03815e70e555c5ef05615658` |
| `modules.json` | `349` | `84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf` |
| `onnx/model.onnx` | `435826548` | `74187b16d9c946fea252e120cfd7a12c5779d8b8b86838a2e4c56573c47941bd` |
| `onnx/model_O1.onnx` | `435730180` | `5c0b47004076ab40bf15a2c52b98a53e985ebb84faaeeb6d2551768f96e384b0` |
| `onnx/model_O2.onnx` | `435666661` | `14d01256f5f3d2245b15b596173bca4367c9405fde5700dd7fb4e110708c1793` |
| `onnx/model_O3.onnx` | `435666516` | `dd55510706038d0817b7d41bf2078f01472e4865190584ad624e8ab79bbcb310` |
| `onnx/model_O4.onnx` | `217894954` | `cab2a54139fc4fd5b8e2a23cb5729ee28dc44cfde685ad3356d533653e635310` |
| `onnx/model_qint8_arm64.onnx` | `110124379` | `c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f` |
| `onnx/model_qint8_avx512.onnx` | `110124379` | `c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f` |
| `onnx/model_qint8_avx512_vnni.onnx` | `110124379` | `c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f` |
| `onnx/model_quint8_avx2.onnx` | `110207323` | `aa5c27172d77bbd1cbae3628cbac4b26d7c12adabff25d2d4285d0f29159b237` |
| `openvino/openvino_model.bin` | `435583684` | `5c3279d833888eaab745e24b652126c5a71375af185ac21aa47e112e2468dec0` |
| `openvino/openvino_model.xml` | `432773` | `a2912e3dbd3426b77984992953998d8026a3d2377104093079e810b53fc51bf6` |
| `openvino/openvino_model_qint8_quantized.bin` | `109974792` | `fde0c650018f5e244f793316b666aaf4758d4e19072f430e59eb2bcc414895ce` |
| `openvino/openvino_model_qint8_quantized.xml` | `741875` | `930bc2a849d48941bb4752d8dac018f0c0ee8709ba023e47aeab4f8bb9c25b59` |
| `pytorch_model.bin` | `438011953` | `a8fd120b1a0032e70ff3d4b8ab8e46a6d01c2cb08ffe7c007a021c1788928146` |
| `sentence_bert_config.json` | `53` | `cabfacded9272091a06ff595a46ef027a76ddf4ac9e77d0fcf11c605748f1667` |
| `special_tokens_map.json` | `239` | `9ef40e9c160511bf3f46ceb71f1471dafa1e9473d5120bb816c36b2efa75f8ba` |
| `tokenizer.json` | `466021` | `b8be2c30ba5dd723a6d5ee26d013da103d5408d92ddcb23747622f9e48f1d842` |
| `tokenizer_config.json` | `363` | `67f2ff7e223518e729869bb3a70f0caf8368fe549383fc11cfe2dfb42fffc268` |
| `train_script.py` | `13123` | `dea86a7066caa55d0c84c343890dfd849714b6affd8b424ba12372a091578cc8` |
| `vocab.txt` | `231536` | `dbd90cb94e2247bd4d4ccaecbf616d2290e66691d7d5e5bb81f063c2d0649ada` |

## Commit B, single attempt, metrics, and gate

Raw Agent ledgers remain outside Git. Commit B contains only the canonical tasks, review summary, and manifest after exactly 128 selected tasks, 96 negative labels, 128 families, and all static checks pass.

The only evaluation namespace is `artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/attempt-1`. It is attempt 1 of 1; there is no retry, replacement namespace, failed-seed retry, attempt-2, blind-v2-002, or blind-v3.

Per Arm/seed metrics use raw Recall denominators 128 and Negative Hit denominators 96. The frozen statistics remain exact paired McNemar plus 10,000-resample paired bootstrap with seed 7170. Repeated seeds on the same tasks are not independent samples.

The pilot-002 gate remains byte- and semantic-bound: Recall@5 mean/every-seed delta >= 0; MRR and NDCG@5 mean/every-seed delta >= -0.01; Negative Hit Rate@5 mean delta <= -0.05 and every-seed delta <= 0; p95 latency mean/every-seed ratio <= 1.20.

## Agent workflow states and permanent posture

```json
{
  "pre_evaluation_states": [
    "AGENT_BLIND_V2_READY_FOR_GENERATION",
    "AGENT_BLIND_V2_READY_FOR_FORMAL_ATTEMPT"
  ],
  "terminal_posture": {
    "default_router_unchanged": true,
    "production_ready": false,
    "release_authorized": false,
    "router_decision": "KEEP_BASELINE"
  },
  "terminal_states": [
    "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
    "AGENT_BLIND_V2_PROTOCOL_INVALID",
    "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
    "AGENT_BLIND_V2_GATES_PASSED",
    "AGENT_BLIND_V2_GATES_NOT_PASSED"
  ]
}
```

Every terminal state records `KEEP_BASELINE`, `production_ready=false`, `release_authorized=false`, and `default_router_unchanged=true`. Even a gate pass is evidence only on this Agent-constructed set.

## Explicit non-actions

No train, optimizer step, mining, tuning, relabeling, threshold change, gate change, seed change, best-seed selection, hard-task deletion, checkpoint mutation, query/skill-representation change, later attempt, replacement blind set, blind-v3, default-router change, merge, tag, release, deploy, or archive. No candidate generation, provider call, receipt creation, model scoring, or formal attempt is part of Task 8.

## Historical supersession note

Commit `09ba4104a147a2f740ef69283c850f40e78a0b15` is retained only as immutable audit history for the superseded external-human 64/48 protocol. It is non-authoritative for generation, review, dataset freeze, or evaluation. No candidate data was seen and no formal attempt started under that commit. No other superseded preregistration commit is part of this active protocol.
