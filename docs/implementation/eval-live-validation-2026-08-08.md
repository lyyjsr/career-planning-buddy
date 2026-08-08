# Eval Live Validation - 2026-08-08

## Scope

This record validates the local Eval V2 path with real providers:

- Agent model: GLM `glm-4.7` through the Zhipu OpenAI-compatible API.
- Judge model: DeepSeek `deepseek-v4-pro` through a separate API account.
- Database: the project's local PostgreSQL container.
- Comparison: B0 `direct_llm_v1` versus B3 `full_agent_v1`.
- No API key or raw model response is recorded in this document.

The run is a smoke/acceptance sample. It is not statistically sufficient to
claim that either variant is better.

## Harness Changes Validated

- B0 uses the common Experiment, Trial, Run, evidence, grader, and report path.
- B0 receives explicit request/profile/planning-window state only.
- B0 run snapshots freeze `available_tools=[]` and
  `career_planning=direct_llm_baseline_v1`.
- B3 run snapshots retain `memory_lookup`, `rag_retrieve`, and `web_search` and
  use `openai_compatible_plan_stage6_context_v1`.
- Pairwise Judge runs use deterministic IDs and both baseline/swapped display
  positions.
- A Judge comparison is skipped unless both Trials completed.
- Provider audit now persists an error row and re-raises the original
  `AgentError`, preserving `PROVIDER_TIMEOUT` across Run and Trial reporting.
- Interrupted Eval recovery now has an automated PostgreSQL regression test.

## Provider Configuration Findings

- GLM needed a 90-second HTTP timeout. At 60 seconds, two B3 calls were
  correctly audited as `PROVIDER_TIMEOUT`; the old audit wrapper then swallowed
  the exception and caused a misleading `STRUCTURED_OUTPUT_INVALID` result.
- DeepSeek reasoning exhausted 800 and 2000 output-token budgets before
  producing `content`. A 4096-token budget completed both position-balanced
  Judge calls.
- The safe empty-content diagnostic records only finish reason, whether a
  reasoning field exists, and completion-token count. It never records hidden
  reasoning or raw response content.

## Recorded Experiments

### Exploratory run

- B0 experiment: `57c82202-89f2-4996-891f-101158ac33ea`
- B3 experiment: `9a6b4a27-f97b-49af-b763-512765d133d9`
- Cases: `create-01`, `replan-01`
- Outcome: two of four Trials completed. The two failures exposed the timeout
  propagation defect described above. One completed Judge result was persisted
  before a second Judge call returned empty content.

### Final valid pair

- B0 experiment: `7669abcd-260c-4ba4-9b08-5a521dad83f3`
- B3 experiment: `bdf08fc4-2d15-440a-8229-068ff8e265f1`
- Case: `create-02` (`Build an internship preparation plan`)

| Metric | B0 Direct LLM | B3 Full Agent |
|---|---:|---:|
| Trial status | completed | completed |
| Latency | 31,195 ms | 20,641 ms |
| Input tokens | 1,165 | 1,916 |
| Output tokens | 2,432 | 748 |
| Total tokens | 3,597 | 2,664 |
| Structured output gate | pass | pass |
| Time budget gate | pass | pass |
| Safety gates | pass | pass |
| Task startability gate | **fail** | **fail** |

Both variants generated all 33 configured deterministic score rows. The
`task.startability` hard gate failed for both, so this case does not pass the
overall hard-gate release condition.

### Post-validation correction

The shared `task.startability` failure was later confirmed to be a Harness
collector defect, not a model-output defect. Both persisted tasks contain a
non-empty `starter_action`, but `_task_projection` omitted that field before
the Task Grader read the frozen outcome. The collector now projects
`starter_action`, and a database-bound regression test verifies both the
evidence field and the final `task.startability` pass result. The historical
Score rows above remain immutable; use a new Experiment for subsequent quality
comparisons rather than interpreting these two failed rows as model quality.

## Pairwise Judge

Pair ID: `820f0ffd-f0dd-48d8-aa6a-b44e17bb5fb7`

| Display position | Normalized verdict | Confidence | Latency |
|---|---|---|---:|
| baseline | tie | medium | 11,703 ms |
| swapped | tie | high | 17,909 ms |

The normalized verdict is stable after swapping. This validates position
normalization for the sample. It does not establish Judge calibration or model
superiority.

## Automated Verification

- Focused B0/provider tests: 16 passed.
- Focused Judge/provider tests after final changes: 40 passed, 1 unrelated
  database-bound test deselected in the host-only run.
- Docker database integration set: 24 passed, including interrupted Eval
  recovery.
- Full backend suite: 541 passed, 1 failed.
- Type checking: 164 source files passed.
- All files changed in this work pass Ruff.

The one full-suite failure is the pre-existing OpenAPI snapshot drift around
generated 422 response descriptions. Full-repository Ruff still reports three
pre-existing findings: two redundant f-string prefixes in migration `0012` and
one unused import in `stage_b1_provision.py`.

## Acceptance Decision

**Pass for campus-project Eval harness execution readiness.** The project can
run, persist, audit, deterministically grade, and independently blind-judge a
real B0/B3 pair.

**Not yet passed for comparative quality claims.** Before presenting a result
such as "Full Agent is better than Direct LLM", run the frozen 30-case Golden
Set (or at minimum a balanced 10-case demonstration set), investigate the
shared `task.startability` failure, and perform a small human spot check of
Judge labels.

## Security Note

The two API keys were supplied in chat text. Rotate both keys after this
validation and update the ignored local `.env`; never commit the current keys.
