## ADDED Requirements

### Requirement: Support diagnostic CI gate productization
The system SHALL allow diagnostic artifacts produced by the onboarding path to
be consumed by a bounded CI gate without changing their unlabeled diagnostic
semantics.

#### Scenario: Use diagnostic artifacts as gate inputs
- **WHEN** scan, lint, inspect, and route artifacts are produced by the
  Diagnostic Onboarding Path
- **THEN** a CI gate MUST be able to consume those artifacts without requiring
  benchmark labels, network access, model downloads, a server, or a SaaS backend

#### Scenario: Preserve zero-label onboarding
- **WHEN** the diagnostic CI gate exists
- **THEN** scan, lint, inspect, route, and diagnostic-dashboard commands MUST
  remain usable outside CI without requiring gate thresholds or benchmark labels
