# Real strong-retrieval path

S calls the actual local `SkillRouter-Embedding-0.6B` and
`SkillRouter-Reranker-0.6B` assets, not a hashing/mock substitute. Configured
revisions are `c03c9bcee9fce92ab0262bb6dcf54d174a8ba558` and
`78986e1142d12857cfd85b8005e62902cd42d858`; measured file digests are in
[model-identity.json](../../artifacts/repo-portability/model-identity.json).
The formatter/pooling/template implementation is attributed to SkillRouter
`2f0c69fe` and retained with its license. This study did not train those models
or rerun a separate upstream parity benchmark.

The actual campaign profile uses MPS, float32, SDPA, batch size 1, left padding,
4096-token encoder and reranker limits. Encoder query text is capped at 2000
characters, descriptions at 500, encoder skill bodies at 8000 and reranker skill
bodies at 2000. Encoder vectors use last-token pooling and normalization.
Retrieval top-k is 20, bounded by the five-package registry. Reranking uses the
reference special-token template and last-token yes/no logit difference; the
final top two packages are presented in common registry order. Full package
exposure is distinct from the shorter text scored by the selector.

Model paths are local-only, remote code is disabled, and nonfinite outputs fail.
Every model constructor hashes the weight/config/tokenizer files. Index identity
includes model identity, profile, registry identity, skill IDs and actual scoring
texts; vector dimensions and finiteness are checked before reuse. Relative paths
resolve from the profile JSON directory. N/F do not import or load these models.

Each confirmation S uses the real online recommend→mount→Agent path. The index
is warmed from the development phase; per-request cache/index, constructor,
retrieval and reranking measurements are reported without disguising cache
reuse as a new cold build. Development contains the separately observed cold
index cost. `latest_load_seconds` is a component already inside the relevant
stage, not an additional amount to sum again. `recommend_wall_seconds` covers
the full recommendation call, while pipeline wall time includes recommendation,
workspace setup, Agent execution, capture and verification.

The declared revision strings plus local file digests identify the used assets;
they are not a claim of cryptographic attestation by the upstream host. Skill
ranking/exposure differences do not themselves establish successful use or
incremental repair utility.
