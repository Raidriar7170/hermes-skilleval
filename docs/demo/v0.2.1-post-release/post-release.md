# v0.2.1 Post-Release Evidence

This file records the post-release facts verified after the explicit human
approval for the `v0.2.1` patch release.

## Release Status

- Published: `true`
- Tag created: `true`
- GitHub Release created: `true`
- Marketplace published: `false`
- Tag: `v0.2.1`
- Target commit: `c667c4d00bddff05c2b5feb357a76182cef2134e`
- Published at: `2026-06-05T06:28:08Z`
- Release URL: <https://github.com/Raidriar7170/hermes-skilleval/releases/tag/v0.2.1>

## Source Evidence

- [`release notes`](../../release-notes/v0.2.1.md)
- [`post-release onboarding cleanup Human Brief`](../../human-briefs/2026-06-05-post-release-onboarding-cleanup.html)
- [`v0.2.1 patch release Human Brief`](../../human-briefs/2026-06-05-v0-2-1-patch-release.html)
- [`v0.2.0 post-release evidence`](../v0.2.0-post-release/post-release.md)
- [`post-release.json`](post-release.json)

## Verification Commands

- `git ls-remote --tags origin 'v0.2.1' 'refs/tags/v0.2.1^{}'`
- `git rev-parse v0.2.1^{}`
- `gh release view v0.2.1 --json tagName,name,url,isDraft,isPrerelease,publishedAt,targetCommitish`
- `PYTHONPATH=src python -m hermes_skilleval.cli release-check`

## Boundary

This records the GitHub tag and GitHub Release only. It is not Marketplace
publication, not GitHub API PR comments, not PR annotations, not SaaS, not a
runtime MCP router, not a SOTA claim, not benchmark status, not production
readiness, and not automatic merge approval. `finetuned-embedding` is not
approved as default.
