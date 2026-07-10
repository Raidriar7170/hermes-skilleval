# portable-training-output-root Specification

## Purpose
Define how embedding-router training selects, validates, and records a portable output root while preserving the `/mnt/data/minghongsun` default and historical evidence.
## Requirements
### Requirement: Training output root is explicitly selectable
The embedding-router training path SHALL select its output root from an explicit `--output-root` CLI value when supplied, otherwise from `output_root` in the training config when present, otherwise from the backward-compatible `/mnt/data/minghongsun` default. A relative selected root SHALL resolve against the trainer process's current working directory, not the config file's directory.

#### Scenario: CLI root overrides config root
- **WHEN** both `--output-root` and config `output_root` are supplied
- **THEN** the CLI root is selected
- **AND** the configured output directory is revalidated against that selected root

#### Scenario: Config root is used without a CLI override
- **WHEN** the CLI omits `--output-root` and the config contains `output_root`
- **THEN** the config root is selected

#### Scenario: Legacy config keeps the A100 default
- **WHEN** both the CLI option and config field are absent
- **THEN** the selected root is `/mnt/data/minghongsun`

#### Scenario: Relative root uses process working directory
- **WHEN** the selected root is relative and the config file is stored in a different directory from the trainer process's current working directory
- **THEN** the canonical root is resolved from the process's current working directory

### Requirement: Output directory is contained by the selected root
The training path MUST canonicalize the selected root and output directory and MUST reject any output directory that resolves outside the selected root. Relative output directories SHALL be interpreted beneath the selected root, and absolute output directories SHALL be accepted only when contained by it.

#### Scenario: Relative output directory stays inside root
- **WHEN** the selected root is `/work/hermes` and `output_dir` is `models/router`
- **THEN** the canonical output directory is `/work/hermes/models/router`

#### Scenario: Absolute output directory is inside root
- **WHEN** an absolute output directory resolves beneath the canonical selected root
- **THEN** validation succeeds without relocating the directory

#### Scenario: Parent traversal escapes root
- **WHEN** a relative output directory uses `..` components that resolve outside the selected root
- **THEN** validation fails before any output is written

#### Scenario: Absolute path escapes root
- **WHEN** an absolute output directory resolves outside the selected root
- **THEN** validation fails before any output is written

#### Scenario: Symlink escapes root
- **WHEN** an existing path component beneath the selected root is a symlink whose target resolves outside the root
- **THEN** validation fails before any output is written

### Requirement: One containment contract serves generic and A100 paths
The system SHALL expose a generic root-containment validator and SHALL retain `validate_a100_user_path()` as a compatibility wrapper using `/mnt/data/minghongsun`.

#### Scenario: Existing A100 caller remains valid
- **WHEN** an existing caller validates a path beneath `/mnt/data/minghongsun` through `validate_a100_user_path()`
- **THEN** it receives the canonical contained path without changing its call contract

#### Scenario: Portable caller selects a local root
- **WHEN** a portable training caller supplies a local root and a contained output path
- **THEN** the same containment semantics return the canonical local output path

### Requirement: Selected root propagates through training provenance
The train config, trainer, model-manifest validation, and `train-run-summary.json` SHALL use the same selected canonical root. New train configs and run summaries SHALL record `output_root`, and summaries SHALL also record the canonical resolved `output_dir`.

#### Scenario: Portable run records its root
- **WHEN** training is configured with a non-A100 output root and reaches artifact writing
- **THEN** model-manifest validation uses that root
- **AND** `train-run-summary.json` records the same canonical `output_root` and contained `output_dir`

#### Scenario: Root mismatch is rejected
- **WHEN** an explicit CLI root does not contain the config's absolute `output_dir`
- **THEN** the trainer exits before directory creation, model save, manifest writing, or summary writing

### Requirement: Portability does not relabel historical evidence
Current commands and documentation SHALL describe the selectable root, but committed historical Phase 14/A100 configs, manifests, summaries, and review evidence MUST retain the paths and provenance of the runs they originally recorded.

#### Scenario: Documentation is updated without evidence mutation
- **WHEN** portability guidance is added
- **THEN** current examples show the A100 default and an explicit alternate-root invocation
- **AND** historical evidence files remain unchanged
