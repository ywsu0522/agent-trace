# HW1 pipeline and agent evaluation

Run all commands from the agent-trace root. The scripts call agent-trace APIs directly; they never import the HW1 Python package. Live always means the local Ollama HTTP server, with no external API or API key.

```powershell
# Original deterministic cases, followed by all local live cases
.venv/Scripts/python.exe -m scripts.test01
.venv/Scripts/python.exe -m scripts.test02

# Separate runs
.venv/Scripts/python.exe -m scripts.test01 --mode deterministic
.venv/Scripts/python.exe -m scripts.test01 --mode live --out runs/my-p01
.venv/Scripts/python.exe -m scripts.test02 --mode live --out runs/my-p02
```

Default local model for both scripts: `qwen3.5:4b-q4_K_M`. The tested 8 GB host profile uses temperature 0, thinking disabled, 4096 context tokens, 12 GPU layers and a prefill batch of 64 to reserve RAM/VRAM headroom. Override with `--model`, `--num-ctx`, `--num-gpu` (0 = CPU), `--num-batch`, `--workers`, `--timeout`, or `--base-url` (loopback only). Classification uses the category/reason JSON schema and token budget exported by the priority API; digest writing stays uncapped plain text. These per-task options and actual native payloads are saved in each run. P02 classification uses two concurrent requests. Each day is generated once and all three checks use the same completion.

P01 runs the 25 original deterministic cases and the 60 emails in `tests/fixtures/priority_gold.json`. Passing requires at least 85% accuracy (51/60), no unknown results, valid output contracts and no inference errors. The reason must be nonempty; it is not compared to a gold explanation.

P02 runs the 8 original deterministic cases and the 5 days in `tests/fixtures/digest_days.json`. It selects exactly `email_ids` from the archive, in fixture order. Each digest must be nonempty and at most 300 whitespace-separated words, contain an alias from every urgent `must_mention` group, and contain no `must_not_mention` term. Matching preserves HW1 normalization and whole-token semantics. Outputs are never truncated to meet the word limit.

P02 reads `.cache/emails.jsonl`; prepare it with `agent-trace prepare-data`, or supply `--emails PATH`. No corpus is downloaded automatically. Ground truth is passed only to evaluation, never to the model. Every run uses a new output folder; reruns never overwrite earlier evidence.

`runs/<run>/` contains `metadata.json` (fixture/corpus/code hashes and model identity), the exact `fixture.json`, incremental `progress.json`, final `results.json`, and a directory for each email/day. Each case includes `events.jsonl` (complete application and Ollama HTTP requests/responses), `settings.json`, `output.json`, and `evaluation.json`. P02 also saves `prepared.json` (classifications and threads) and `written.json` (the unmodified digest). Nonzero exit status means a test failed or inference could not complete; failed cases and exceptions are reported explicitly.

The ported deterministic tests preserve original cases and expected behavior, with imports and model doubles adapted for this independent package. `tests/test_pipeline_evaluation.py` additionally checks scoring, filtering, raw-output preservation and trace finalization offline.

To fit local RAM, the P02 writer receives full urgent threads, a source-derived urgent-subject list, and short source excerpts (up to 250 characters) for at most three normal threads. The writing prompt targets at most 220 words, while evaluation retains the original 300-word limit. Full original evidence stays in `prepared.json`; the generated completion is never clipped.

The models must already be installed in Ollama (`ollama pull qwen3.5:4b-q4_K_M` if needed); these scripts do not download them automatically. P01 and P02 record their selected model and exact settings separately.


If only the P02 writing prompt changes, explicitly reuse completed classifications:

```powershell
.venv/Scripts/python.exe -m scripts.test02 --mode live --reuse-classifications runs/previous-p02 --out runs/new-p02
```

This requires the same model settings, model digest and priority implementation. Only byte-equivalent classification messages are matched; new inputs still invoke Ollama. Every reused response must have matching original native HTTP evidence. Reuse is recorded as `classification_replay` with the original file hash and call ID, and never creates fake HTTP events. All five writing calls remain fresh local inference; summaries report both reused classifications and fresh model calls. Source runs are kept intact and may have failed output checks, but must have completed every day without inference errors. Writer completions and GT are never used as classification cache entries.

Priority makes one rubric-based classification call and parses its category/reason reply, preserving legacy label-only replies. The original classifier logic is retained; raw completions and parsed outputs are separately recorded, and no GT enters this step.


## P03, P04, P05 and P07 deterministic evaluation

These entry points run only deterministic tests and need no Ollama server:

```powershell
.venv/Scripts/python.exe -m scripts.test03 --mode deterministic
.venv/Scripts/python.exe -m scripts.test04 --mode deterministic
.venv/Scripts/python.exe -m scripts.test05 --mode deterministic
.venv/Scripts/python.exe -m scripts.test07 --mode deterministic
```

`--mode deterministic` is optional; it is the only supported mode for these four scripts. Each accepts `--out NEW_DIRECTORY`. P03 also accepts `--emails PATH` (default `.cache/emails.jsonl`). Prepare that archive explicitly with `agent-trace prepare-data --archive PATH` or `agent-trace prepare-data --download`; the test runners never download data. P03 verifies the complete archive's checksum and 26,278-email count before archive tests; a missing or different corpus fails instead of skipping tests or substituting a subset.

| Script | Original deterministic cases | Direct application API |
|---|---:|---|
| `test03` | 18 | `agent_trace.pipelines.bm25.build`, `rank` |
| `test04` | 12 | `agent_trace.pipelines.email_qa.answer_email_question` |
| `test05` | 44 | `agent_trace.agent.registry.ToolRegistry` |
| `test07` | 31 | `agent_trace.agent.session.AgentSession` with `ToolRegistry` |

The port preserves original test inputs, parametrization and assertions. Imports and adapter calls use independent local APIs. `tests/scripted_lm.py` ports only the provider-free scripted model; `tests/fixture_tools.py` retains the original synthetic tool schemas and behavior. P07 formats its scripted calls through the existing `agent_trace.agent.protocol.format_tool_call`; P06's own test suite is outside these runs. An `offline_only` fixture blocks provider requests and socket connections for all four suites.

Each run writes `metadata.json` (command, Python version, code/fixture hashes and the P03 corpus hash), `pytest.log`, `junit.xml` (individual results and captured output) and `results.json`. Default folders are `runs/pXX-deterministic-TIMESTAMP/`. A nonzero pytest exit, any failed/error/skipped case, or a case count different from the original makes the script fail. P03 includes the original numeric score, full-archive recall and timing tests; run it without competing workloads when assessing its time limits.


P03's timing checks exposed a query-time bottleneck on this host. The BM25 index now stores each document's query-independent length-normalization factor, while term contributions and query scores are still computed at search time. The first matching term initializes scores directly, avoiding repeated missing-key lookups and additions to zero; later terms accumulate normally. The original scoring formula, test cases and timing thresholds remain unchanged.

## P09 current-agent baseline

`python -m scripts.test09` runs the original `doc_questions.json` d01-d20 in order through the existing CLI, creating a fresh AgentSession per question. It uses the current prompt and model settings unchanged, with no repair or response reuse. `--out NEW_DIRECTORY` selects a new result folder.

The runner saves the fixture/configuration/prompt, source hashes, per-question raw HTTP evidence and traces, incremental `progress.json`, and final `results.json`/`README.md`. It continues after individual inference failures and records them explicitly. Answer aliases, the 6000-token document-result limit and reference-line exposure are evaluated after generation; evidence support is not semantically judged. The document-result limit is currently a scoring rule rather than a hard agent-loop stop.

The [2026-11-04 batch and subsequent evidence review](../studies/doc-baseline-20261104/README.md) are archived together. Its original automatic scores remain unchanged; review is a separate sidecar covering every answer, added claims, citations and stopping behavior. Completing the batch runner alone does not finish that review.

## Bounded document refinement study

`python -m scripts.refine_docs --source studies/d06/record/runs/protocol-after --task d06` prepares a retrospective review-only versus continue-then-review comparison without inference. Add `--mode live` for local Ollama; each condition permits at most one model call, and continuation allows one extra document read by default. Both consume the original run's document-result budget; no gold selects the continuation or final answer. Outputs include source/code hashes, native HTTP evidence, raw answers and cost accounting in a new `runs/` folder.

This is an archived-draft intervention, not a fresh current-agent benchmark or a full Self-Refine reproduction. See [scope, controls and limits](../docs/qa-development.md).
