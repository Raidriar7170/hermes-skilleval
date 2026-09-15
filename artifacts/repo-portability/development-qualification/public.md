# feat(in2csv): add format detection via extension for ndjson

Source: https://github.com/wireservice/csvkit/pull/1345
The public PR has no description. Its title requests automatic format detection
for NDJSON. Base documentation already describes `--format ndjson`.

Public replay clarification, shared by every arm: recognize `.ndjson`, `.jsonl`
and `.jl` extensions as NDJSON in the existing format guessing API and in2csv
CLI without requiring an explicit format argument. Preserve JSON, CSV and the
other supported extensions. This is a repository maintenance task, not a
one-off file conversion. No exact implementation is required.
