# Development slice (historical checkpoint)

This page records the first csvkit slice, not the final delivery status. See the
[review index](review-index.md) for the study and current limitations.

The active execution contract is [the Goal](../goals/Hermes_Two_Repo_Fixed_Baseline_GitHub_Goal.md).

First real second-repository slice: csvkit PR 1345, base
`2a40ee24bf405a4a007fe822850fb3ee75fb21bf`, reference
`aa4d9ce318c7da5a963a338baf9b9f6bffcd4c70`.

The shared verifier observed all six target tests fail on base, all pass on
reference, and seven related regressions pass on both. Explicit fresh rebuilds
accepted the reference patch and rejected no-op. Native attempt 1 produced a
real patch that passed the same six target and seven regression tests.

The public request includes an explicit clarification covering three extensions
and both API/CLI; this clarification is available to every arm. This is a
development task, not confirmation evidence. The controller selected it before
observing Agent outcomes. Large examples/realdata are excluded consistently
from both exported revisions; other original source and documentation remain.

Preparation errors retained locally: unsupported system Python archive filter;
then oversized upstream example data. No Agent had started in these failed
preparations. Python 3.12 and explicit export exclusions resolved these causes.

No study completion, algorithm gain, arbitrary-repository support or upstream
adoption is claimed. Public patches and JUnit are sanitized derivatives under
artifacts/repo-portability; no raw conversations or authentication files belong
in this branch. The initial development image inherits a local prerequisite and
is not a clean-install demonstration. The later confirmation uses the separately
built clean image and installed wheel described in the review index. All three
saved development patches received the separate audit described in the evidence
boundary; those audits did not invoke new Agents.
