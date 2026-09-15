# Third-party source and evidence

- Public csvkit source excerpts, trusted tests and patches refer to
  [wireservice/csvkit](https://github.com/wireservice/csvkit) revisions pinned in
  each task. Its [MIT notice](csvkit-COPYING) is preserved from
  `8119565ce5b2c28d1dbb8fcd93907d6fb823e726`.
- Public sqlite-utils source excerpts, trusted tests and patches refer to
  [simonw/sqlite-utils](https://github.com/simonw/sqlite-utils) revisions pinned
  in each task. Its [Apache 2.0 license](sqlite-utils-LICENSE) is preserved from
  `2d3c6b9a1e5068fcee6923c9ed74cbd158ee9db4`.
- SkillRouter implementation attribution/license is retained in
  [the vendor license](../../../src/hermes_skilleval/vendor/SkillRouter-LICENSE).
  Model weight files are not redistributed; only their identity digests and
  revision strings are published.
- The two public Superpowers-derived skill packages retain their own source
  and MIT license notices in `configs/repo-portability/skills-v1`. The other
  three are explicitly Hermes-derived workflow packages, not external evidence
  of independent skill quality or task-specific solutions.

Public issue/PR bodies are attributed with source URLs per request. Historical
source and byte-preserved notices are not rewritten to match project formatting.
