# Adaptive Skill Intervention — research prototype

This additive experiment asks whether one explicit skill intervention, selected from the current observable maintenance state, improves terminal utility over continuing without external guidance. Existing maintenance and routing defaults, PR #48 results and prior evidence remain unchanged. The active contract is [the saved Goal](../../goals/Hermes_vNext_Adaptive_Skill_Intervention_Codex_Goal.md).

**Execution status:** formal collection is running; training, independent model reload and the final 96-run matrix are not yet complete. The following describes the frozen method, not a claim of measured improvement.

## Frozen protocol

Twelve train mechanisms, four previously observed development mechanisms and eight mechanism-held-out test tasks come from sqlite-utils, csvkit and csv-diff. Public issues may have appeared in the execution model's pretraining; this is not a contamination-free benchmark. The four repeatedly observed development mechanisms never enter the final test split. Task refinements are public in each task request before execution; source links and request hashes appear in the protocol. Full external source snapshots, raw traces and weights stay outside Git.

Each trajectory uses Codex 0.154.0, `gpt-5.6-sol`, medium reasoning and a 600-second activity budget in the inherited isolated Docker execution boundary. Source and scratch copies, session setup, model turns, state extraction, snapshots, online scoring and teardown count against the original budget. Process stop latency can overrun the wall-clock deadline; utility time is capped at one, and any overrun is separately observable in the execution record. No branch receives a fresh 600 seconds.

E0 is the common empty-history task state. E1 follows the first observed public test failure or repeated tool error at a completed turn boundary. E2 follows candidate delivery or consumption of 75% of the activity budget. Missing opportunities remain absent. All methods and offline tails use the same neutral continuation schedule, including the final opportunity; a no-op still executes. No artificial error is introduced to trigger E1.

For nonempty histories the adapter uses official `thread/fork`, verifies the returned public history against the checkpoint digest and restores independent source/scratch snapshots at the same logical container paths. Public `thread/read` and completed tool events provide the history; internal rollout files and private reasoning are not parsed. Hidden RNG state is not cloned: these are observable-prefix paired samples, not exact individual counterfactuals. Agent tools cannot read the controller-owned session store or hidden verifier assets.

At every natural training/development opportunity, the action roster is no intervention, static top skill, dynamic top distinct skill and generic reminder. A fixed 12-state potential roster receives a second repetition if the state actually occurs. Maximum collection size is 240 tails, plus native prefixes. Every attempted sample is retained. Infrastructure errors produce unknown labels rather than negative skill labels.

## Representation and decision

The original ten-skill catalog is unchanged. Static retrieval embeds the request and repository description. Dynamic retrieval averages separately encoded request, public failure and current source, so a long request cannot truncate away state. The frozen MiniLM encoder uses revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, a 256-token limit per field and mean pooling. Actual pretrained weights are required; there is no random/hash representation fallback.

Full state combines task representation, separately encoded failure/source/diff and numeric progress/budget features. The skill and state projections have width 64, and the gain head receives their concatenation, product and difference. Huber plus a small within-state ranking term supervises measured paired utility differences. Task/state weighting and averaging fixed repeats avoid treating shared no-op tails as independent mechanisms. Gain is unrestricted, with no-intervention gain fixed at zero.

The wait model learns from subsequent naturally observed no-op states. Nested leave-task-out fitting excludes the target task from both gain and downstream wait models that generate its target. Targets use predicted next-state value, never the realized best future branch. Online prediction receives only the current state. Ties preserve the one remaining intervention; E2 wait value is zero. `METHOD_UNAVAILABLE` is separate from model-chosen waiting or no-op.

The no-state arm independently fits gain and waiting networks using task/repository, stage and budget, with static candidates. It does not simply mask a full-state model at deployment. Myopic uses the same full-state gain model without consulting the wait model. N0, S1, R1, H-myopic, H-no-state and H-full each run twice on all eight final mechanisms: 96 actual complete trajectories. Final policies execute only their selected continuation, never online candidate search.

## Labels and limits

The controller reconstructs the actual captured patch on a clean base and runs source-grounded hidden target checks and protected regressions after every relevant task's Agent executions have ended. File-policy violations count as unsuccessful candidates. Patch capture preserves prohibited edits before rejection. Check infrastructure failures remain unknown. Task qualification requires a passing reference plus a rejected functional negative with protected regressions still passing; three already-green bases remain legitimate no-op cases.

Utility is `success - 0.05 * min(active_seconds / 600, 1) - 0.02 * min(guidance_tokens / 1200, 1)`. Success always dominates cost. The token counter is explicitly an `o200k_base` proxy: installed tiktoken has no exact `gpt-5.6-sol` mapping. Paragraph-bounded payloads are at most 1,200 proxy tokens. Exact provider guidance tokens and the monetary bill are **UNAVAILABLE**, not inferred from this proxy.

The predetermined development diagnostics compare skills with generic reminders and compare E2 forced injection with allowing no-op using only supported observed actions. They are not additional end-to-end test arms. Final uncertainty uses task-clustered paired bootstrap; two repetitions and multiple states are not additional independent tasks. With eight final mechanisms, intervals are unstable and non-significance does not establish equivalence.

## Execution and records

See [commands](commands.md) for preparation, collection, fitting, independent-process reload, comparison and records-only replay. Research outcomes are reported separately from successful implementation and training. No routing support certification or default promotion follows from this prototype.

The initial preflight freeze was superseded before the first research model call solely to pass the same retriever into offline tails, preserving subsequent retrieval overhead. The original preflight manifest remains in Git; raw collection remains bound to private `protocol-v2.json`, archived publicly as `protocol-collection-v2.json`. The active public protocol now binds private `protocol-v3.json` for revised labels and final evaluation.

During collection, independent review confirmed a checker adapter defect in four training tasks (202, 223, 228, 250): simulated Click stdin lacks file-descriptor interfaces used by their historical CSV import implementations. The versioned repair writes identical CSV/TSV/BOM bytes to actual temporary files, matching the public requests and retaining all feature assertions. Four bases remain target-red/regression-green and references target-green/regression-green. Raw executions, source patches, budgets, action roster and file-policy verdicts remain unchanged. Every affected saved branch/repeat is rechecked symmetrically without Agent resampling; original verdicts remain alongside revised verdicts. Training waits for the derivative records. This post-observation checker repair is a disclosed validity limitation, not a new sampling opportunity.

## Related mechanisms

[HASP, section 3.1](https://arxiv.org/html/2605.17734v1#S3.SS1) defines executable activation and intervention functions around an agent loop, including action revision and context injection. ASI uses bounded textual payloads at completed boundaries; it does not implement HASP's program-function evolution or train the base Agent.

[SkillGen, sections 2 and 3.3](https://arxiv.org/html/2605.10999v1) compares skill and no-skill outcomes and counts both repairs and regressions. ASI adopts that net-effect discipline while learning a state-dependent one-use stopping policy. It does not reproduce SkillGen's skill synthesis or iterative skill selection. Neither reference demonstrates utility for this implementation; that requires the frozen local comparison.

Before training, independent review corrected unknown-label handling: all real checkpoint states remain in the no-op chain, even if none of their paired labels is usable. Unconfirmed termination and unavailable downstream fold predictions are missing wait targets, not synthetic zero values. Confirmed terminal states retain real zero wait targets. The model metadata binds the collected record digest and protocol, encoder, catalog and payload identities; independent reload binds the actual weights and model metadata.

The contract's state-only diagnostic is a separate fixed 160-epoch, seed-7170 gain head with the request/repository vector zeroed. It uses the existing train/dev pairs and full candidate roster, is saved and independently reloaded, and adds no final runtime arm or hyperparameter search. H-no-state is a broader removal of dynamic information, including dynamic candidate retrieval; differences from H-full cannot be attributed solely to network input features. Its static second candidate can lack direct action coverage, which must be reported as model extrapolation.

Before the first final-policy run, additive timing instrumentation was enabled for state recognition, retrieval, checkpointing and decision/scoring. These durations remain inside the original activity budget; they do not add execution time or change the policy. Raw collection predates these separate timers, so its component overhead is unavailable rather than zero. Final reporting includes measured-run coverage. Development E2 opportunity loss is computed only over valid observed deployable actions and is a stochastic post-hoc diagnostic, never a wait target or an estimate of the full WAIT trajectory.

Reported token accounting is extracted offline from public `thread/tokenUsage/updated` events during newly started turns. Resumed/forked prefix notifications and duplicate updates are excluded; cumulative counters must agree with each request increment when a preceding counter is available. Collection tails and native prefixes are reported separately, with per-run coverage and interrupted-turn visibility. These are provider-reported tokens, not a monetary bill or a substitute for the frozen guidance-length proxy.
