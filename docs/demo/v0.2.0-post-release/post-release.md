# v0.2.0 Post-Release Evidence

This file records the post-release facts verified after the explicit human GO
for `v0.2.0`.

## Release Status

- Published: `true`
- Tag created: `true`
- GitHub Release created: `true`
- Marketplace published: `false`
- Tag: `v0.2.0`
- Target commit: `13af31ee4fd2e9eed4a40f643284120bc5afab9e`
- Published at: `2026-06-04T14:06:56Z`
- Release URL: <https://github.com/Raidriar7170/hermes-skilleval/releases/tag/v0.2.0>

## Source Evidence

- [`release notes`](../../release-notes/v0.2.0.md)
- [`pre-publish final approval checklist`](../v0.2.0-final-approval/final-approval.md)
- [`pre-publish release decision`](../v0.2.0-release-decision/release-decision.md)
- [`post-release.json`](post-release.json)

## Verification Commands

- `git ls-remote --tags origin 'refs/tags/v0.2.0' 'refs/tags/v0.2.0^{}'`
- `git rev-parse v0.2.0^{}`
- `gh release view v0.2.0 --json tagName,isDraft,isPrerelease,name,url,publishedAt,targetCommitish`
- `PYTHONPATH=src python -m hermes_skilleval.cli release-check`

## Boundary

This records the GitHub tag and GitHub Release only. It is not Marketplace
publication, not GitHub API PR comments, not PR annotations, not SaaS, not a
runtime MCP router, not a SOTA claim, not benchmark status, not production
readiness, and not automatic merge approval. `finetuned-embedding` is not
approved as default.
