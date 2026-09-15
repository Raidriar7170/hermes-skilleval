## Context

Active Goal sections 6–14 define the design. Existing runner uses private filesystem capture, separate offline build and verification containers, and real SkillRouter. Public branch starts at verified remote main; prerequisite imports are explicitly listed.

## Goals / Non-Goals

Goals: two qualified repository profiles, a wheel-installed CLI, fixed K=2 baseline and new real N/F/S records. Non-goals: training, third selector, general plugin system, legacy record mutation, merge or release.

## Decisions

Extract only environment/package/entrypoint and test configuration required by csvkit into typed profiles. Reuse capture, clean rebuild, transport and verifier; retain T compatibility. Fixed selection takes only repository profile; native/fixed paths lazily avoid heavy model imports. Relative paths resolve against configuration location. Preparation and qualification remain controller-only. Confirmation protocol freezes before Agent starts; retain every attempt.

## Risks / Trade-offs

Candidate Python is untrusted → preserve isolated containers and trusted bootstrap; no claim of complete malicious Python resistance. Public export can leak history → import an allowlist from clean main and inspect every new commit. Small sample → exploratory conclusions and task-level clustering; no equivalence claims. Resource failure → report actual partial state, never replace S with synthetic retrieval.
