# Agent Skill Routing Reliability

This context defines the language for evaluating whether coding agents can
select the right external skills without activating plausible but wrong ones.
The project is framed as a developer-facing reliability toolkit, not as a
leaderboard or production-readiness claim.

## Language

**Agent Skill Routing Reliability Toolkit**:
A developer-facing toolkit for checking whether an agent can choose appropriate
skills from a growing skill library and avoid unsafe near-miss selections.
_Avoid_: SaaS dashboard, SOTA benchmark, leaderboard

**Skill Library**:
A bounded collection of agent-facing capabilities, where each skill has
activation cues that a router can inspect. One **Skill Library** contains many
**Skills**.
_Avoid_: benchmark corpus, model registry

**Skill Library Maintainer**:
A developer who owns or reviews changes to a real agent skill/tool library and
needs to prevent wrong-skill activation as the library grows.
_Avoid_: generic open-source user, recruiter

**Universal Skill Adapter**:
A normalization layer that turns real skill folders and tool schema files into a
shared **Skill Index** so the toolkit can evaluate user-owned libraries rather
than only the built-in benchmark.
_Avoid_: benchmark generator, importer

**Skill Source**:
A real origin supplied by a **Skill Library Maintainer** for scanning, such as a
Markdown skill folder or an MCP tool schema file. Source scope is discussed by
stable input shape before platform brand.
_Avoid_: platform promise, path list

**Skill Index**:
A portable representation of a **Skill Library** after scanning, containing the
skill identity and routing cues needed by routers, conflict inspection, and
release gates.
_Avoid_: dataset, report

**Skill Scan**:
A normalization pass that discovers **Skill Sources** and writes a
source-annotated **Skill Index**. It preserves provenance and structural parsing
warnings, but does not own quality diagnosis or routing decisions.
_Avoid_: lint, inspect, benchmark

**Skill Lint**:
A quality diagnosis of individual skills, focused on whether their descriptions,
activation cues, and boundaries are clear enough for routing.
_Avoid_: scan, release gate

**Routing Clarity**:
How clearly a skill states when it should and should not be selected, using
specific activation cues and boundaries that distinguish it from nearby skills.
_Avoid_: writing polish, documentation style

**Routing Query**:
A user task used to ask a **Skill Router** which skills should be considered.
It is a practical interaction with a skill library, not a benchmark label by
itself.
_Avoid_: benchmark task, prompt sample

**Route Evidence**:
The visible cues that explain why a skill was selected for a **Routing Query**,
such as matched terms, source fields, boundaries, or category signals.
_Avoid_: opaque score

**Route Risk Flag**:
A warning attached to a routed skill candidate when the selection may be unsafe
or ambiguous, such as a near-miss conflict or weak boundary evidence.
_Avoid_: failure verdict, release decision

**Diagnostic Artifact Contract**:
The stable JSON outputs from scan, lint, inspect, and route workflows that let
later CI gates compare library changes without reinterpreting free-form text.
_Avoid_: presentation output, dashboard payload only

**Unlabeled Diagnostic Mode**:
A zero-label workflow where a **Skill Library Maintainer** can scan, lint,
inspect conflicts, and route example queries without first authoring benchmark
labels.
_Avoid_: benchmark, release gate

**Diagnostic Onboarding Path**:
The first user journey for a **Skill Library Maintainer**: scan a real library,
diagnose individual skill quality, try routing queries, and inspect conflicts
before adding benchmark labels.
_Avoid_: experiment phase, release workflow

**Diagnostic CLI Front Door**:
The user-facing command vocabulary for the **Diagnostic Onboarding Path**. It
should speak in maintainer actions such as scanning, linting, routing, and
inspecting rather than internal benchmark operations.
_Avoid_: evaluation backend, experiment command set

**Labeled Regression Mode**:
A stricter workflow where tasks include expected and negative skills, allowing
the toolkit to measure regressions and enforce a **Release Gate**.
_Avoid_: exploratory inspection, zero-config mode

**Public Routing Benchmark**:
A shared benchmark preset for comparing skill-routing behavior across libraries
or routers. It is follow-up evidence and onboarding material, not the first
product surface.
_Avoid_: P0 product identity, SOTA claim

**Skill Router**:
A selection policy that ranks or chooses skills from a **Skill Library** for a
user task. A **Skill Router** may be deterministic or learned, but the domain
concept is the selection policy rather than the model implementation.
_Avoid_: model, classifier

**Routing Reliability**:
The ability of a **Skill Router** to retrieve relevant skills, reject tempting
wrong skills, and preserve that behavior when the skill library changes.
_Avoid_: raw accuracy, model quality

**Negative Skill**:
A plausible but wrong skill for a task, especially one that shares language,
category, or trigger terms with the correct skill.
_Avoid_: irrelevant skill, random distractor

**Routing Regression**:
A change that makes routing less safe or less useful, such as losing a correct
skill, selecting a new **Negative Skill**, or worsening accepted negative
selections.
_Avoid_: failure, bug

**Release Gate**:
A conservative decision point that decides whether a candidate **Skill Router**
or skill-library change may become the default. The gate protects **Routing
Reliability** rather than celebrating isolated metric gains.
_Avoid_: launch checklist, performance win

**Runtime Skill Router**:
A later integration that serves route candidates to an agent during execution.
It depends on the diagnostic CLI being trustworthy first.
_Avoid_: P0 diagnostic workflow, release gate

**Skill Conflict Map**:
An inspection view of high-risk overlap inside a **Skill Library**, especially
where related skills need clearer boundaries to reduce **Negative Skill**
selection.
_Avoid_: leaderboard, dashboard

**Diagnostic Dashboard**:
A static inspection surface for the **Diagnostic Onboarding Path**, focused on
source summary, routing-readiness findings, and **Conflict Risk Clusters**.
_Avoid_: SaaS UI, runtime console

**Conflict Risk Cluster**:
A group of skills that share enough routing cues to deserve maintainer review.
It is an explainable risk signal, not a claim that the skills are definitely
wrong or must be merged.
_Avoid_: conflict verdict, duplicate detection

**Conflict Signal**:
An interpretable clue that skills may be hard to route apart, such as overlapping
names, trigger terms, descriptions, categories, missing boundaries, or repeated
co-appearance in top-k routes.
_Avoid_: LLM judgment, hidden score

## Flagged Ambiguities

**Market value** now means usefulness to developers maintaining real agent skill
libraries, not a hosted SaaS product or an academic benchmark ranking.

**First users** are Skill Library Maintainers working with real coding-agent
skills or tools, not benchmark readers looking for a leaderboard.

**Adapter scope** starts with stable Skill Source shapes: Markdown skill folders
and MCP tool schemas. Platform names help users recognize examples, but should
not define the first version's domain boundary.

**Value without labels** comes from Unlabeled Diagnostic Mode. Gold and negative
labels are required only when the user wants Labeled Regression Mode and release
gate decisions.

**P0 product value** is the Diagnostic Onboarding Path. Release gate
productization follows after users can already inspect and route their real
skill libraries without labels.

**CLI naming** should expose the Diagnostic CLI Front Door for first-time users.
Existing evaluation-oriented commands can remain as deeper benchmark machinery.

**Skill Lint scope** is Routing Clarity. It should not become a general Markdown
or prose style linter.

**Skill Conflict Map scope** is explainable Conflict Risk Clusters. It should
surface review-worthy overlap rather than make opaque or definitive conflict
judgments.

**Routing Query output** should contain top-k skill candidates, Route Evidence,
and Route Risk Flags. It should not be presented as a pure score leaderboard.

**Runtime integration** such as an MCP server is follow-up productization. It is
not part of the P0 Diagnostic Onboarding Path.

**Dashboard scope** is static diagnostic inspection. It should not become a
SaaS-like product UI or runtime console in P0.

**CI gate productization** follows the Diagnostic Artifact Contract. P0 should
produce stable artifacts, while P1 owns pull-request annotations and merge
blocking.

**Benchmark** remains evidence for routing behavior. It is not the product
identity unless explicitly qualified as a public routing benchmark.

**Public benchmark growth** follows the diagnostic product surface. Larger
benchmark presets should not displace the first user journey of inspecting a
real user-owned skill library.

## Example Dialogue

Developer: "My agent has many browser, MCP, and workflow skills. Which ones are
conflicting?"

Domain expert: "Start with the Skill Library, then inspect the Skill Conflict
Map. The concern is not whether one router has a higher headline score, but
whether Routing Reliability degrades when a plausible Negative Skill appears."

Developer: "If a learned Skill Router improves recall but selects a new negative
skill, should we promote it?"

Domain expert: "No. The Release Gate should keep the safer default when a
Routing Regression appears, even if one metric looks unchanged or better."
