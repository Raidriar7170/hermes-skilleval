## ADDED Requirements

### Requirement: Router query formatting is prompt-only and metadata-incapable
The system SHALL expose `router_query_text(prompt: str) -> str` as the only formatter for a router task query. The formatter MUST accept exactly one non-empty, loader-normalized prompt string and MUST return that string unchanged. It MUST NOT strip, normalize again, concatenate, serialize, enrich, or otherwise transform the prompt, and its API MUST NOT accept a task object, row, metadata mapping, task ID, category, difficulty, robustness tags, split, family, or optional context.

#### Scenario: Loader-normalized prompt is returned unchanged
- **WHEN** a caller passes a non-empty loader-normalized prompt string to `router_query_text`
- **THEN** the returned string is identical to the input string
- **AND** no prefix, suffix, separator, metadata value, or second query representation is added

#### Scenario: Empty or metadata-capable input is rejected
- **WHEN** a caller passes an empty string, a non-string value, a task object, a row, or a metadata mapping instead of the required prompt string
- **THEN** the formatter rejects the input
- **AND** it does not infer or recover a prompt from the rejected value

### Requirement: Every core router consumer shares the formatter
Embedding-pair export used by `embedding_training`, `EmbeddingRouter`, `KeywordRouter`, `HybridRouter`, verification-gated scoring, `CrossEncoderReranker`, router CLI evaluation and comparison, and Stage 2 core routed-prediction export SHALL derive their task-side query only through `router_query_text`. None of these paths MAY retain a legacy, alternate, composite, category-enriched, or metadata-enriched query builder. Category-derived bonuses, affinities, weights, gates, or tie-breakers MUST NOT affect core scores, ranks, or acceptance decisions.

#### Scenario: Core consumers capture the same prompt-only query
- **WHEN** every listed core consumer processes the same loader-normalized prompt
- **THEN** the task-side query captured by each consumer equals the formatter output byte-for-byte
- **AND** no listed consumer captures a legacy, alternate, composite, or metadata-enriched query

#### Scenario: CLI and Stage 2 use the production query contract
- **WHEN** router CLI evaluation, router CLI comparison, or Stage 2 core routed-prediction export scores a task
- **THEN** its task-side query is produced by the same `router_query_text` formatter used by the runtime routers
- **AND** it does not reconstruct a query from benchmark metadata

### Requirement: Task metadata is invariant for scoring and acceptance
With the loader-normalized prompt held fixed, changing task ID, category, difficulty, robustness tags, split, or family metadata MUST leave the captured query, all router and reranker scores, ranked ordering, and verification or routing acceptance decision unchanged. Category words that occur naturally inside the prompt remain ordinary prompt text. Structured task metadata MAY be retained beside an output for record identity, validation, split handling, auditing, or provenance, but it MUST NOT influence model input, score, rank, gate, tie-break, or acceptance.

#### Scenario: Fixed prompt survives all metadata mutations
- **WHEN** task ID is changed to `LEAK_TASK_ID` and category, difficulty, robustness tags, split, and family are each mutated in valid isolated fixtures while the loader-normalized prompt and skill candidates remain fixed
- **THEN** the captured query, scores, ranked ordering, and acceptance decision remain identical
- **AND** no mutated metadata value appears in a task-side query or scoring feature

#### Scenario: Structured provenance remains non-scoring
- **WHEN** a routed or evaluated result includes task metadata as structured output provenance
- **THEN** changing only that provenance leaves scores, ranks, gates, and acceptance unchanged
- **AND** the metadata is not concatenated into the prompt-only query

### Requirement: Skill metadata may remain a separate candidate input
A router or reranker that compares a task query with a skill candidate MAY receive skill text or structured skill metadata as a distinct second input. The allowed skill-side input MUST remain separate from `router_query_text`, MUST NOT provide a channel for task metadata, and MUST NOT change the requirement that the task-side query is exactly the loader-normalized prompt.

#### Scenario: Cross-encoder receives a separate skill input
- **WHEN** a cross-encoder or other pairwise scorer evaluates a prompt against a skill candidate
- **THEN** the first task-side input is exactly `router_query_text(prompt)`
- **AND** any skill text or skill metadata is supplied only as the separate candidate-side input
- **AND** no task metadata is copied into either input
