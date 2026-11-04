# Current agent: reviewed 20-question document QA baseline

The current prompt completed d01–d20 with **18/20 answer alias matches** and **18/20 core answers supported by evidence actually sent to the model**. The document-result budget was met on 19/20 questions. The batch did not pass its complete acceptance rule because d18 exceeded that budget. These are development-fixture results, with no held-out generalization claim.

The batch ran on 2026-11-04, 22:29–23:43 (UTC+08:00), with `qwen3.5:4b-q4_K_M`, temperature 0, thinking disabled and `num_ctx=8192`. Each question used a fresh `AgentSession`. The 78 main-model requests and responses are preserved; there were no auxiliary calls, answer repair or response reuse. Prompt, model digest, fixture, source and corpus hashes are recorded in [metadata.json](metadata.json) and the per-question metadata. [Raw batch summary](batch-summary.md) · [Automated results](results.json)

## Evidence review

All 20 final answers were reviewed after generation against their actual tool results, subsequent HTTP messages and the fixed corpus. This was one Codex assistant review, not an independent multi-rater assessment or the course grading model. No new model calls were made for review.

| Measure | Result | Meaning |
|---|---:|---|
| Answer alias match | 18/20 | Normalized whole-token aliases; not semantic grading |
| Core answer supported | 18/20 | The requested fact appears in evidence sent to the agent |
| Full response factual support | 17 supported, 1 partial, 2 unsupported | Added claims assessed separately from the core fact |
| Within document-result budget | 19/20 | 6,000 course-estimated tokens; scored after generation |
| Source type mislabeled | d08, d14, d15 | Document IDs incorrectly called Email IDs |
| Final native length stop | d06, d18 | Both were still marked `done` by the session |

[Complete per-question review and supporting excerpts](evidence-review.md) · [Machine-readable review](evidence-review.json). Citation labeling and wording warnings can overlap supported answers; these columns are not interchangeable pass rates. Original automated `evidence_support: not_reviewed` fields are preserved, with the later review stored separately.

## Failures and next work

- **d06:** searched without reading the API spec, did not establish the shutdown date, and treated snippet omissions as evidence of absence.
- **d18:** did not read the security policy, drifted into email search and used 6,082 document-result tokens without finding the extension.
- Both final native responses stopped with `done_reason=length`; prompt plus completion counts reached 8,192. The current adapter/session accepted those truncated outputs as final text. No truncation-handling fix is claimed by this baseline.
- **d20:** the annual amount is supported, but the snippet stops before the eligibility list. Its added applicability claim is only partially grounded in what the agent saw, even though the full source confirms it afterward.
- The current loop does not enforce the 6,000-token document-result budget during execution. Retrieval/navigation, stopping behavior, budget enforcement and citation precision remain development work before a new controlled comparison.

## Inspect and reproduce

```sh
# Read or rebuild a report offline; does not contact the model
uv run agent-trace report studies/doc-baseline-20261104/d06 --out runs/baseline-d06-report

# Start a new full batch with the current checkout; requires local Ollama and prepared email data
uv run python -m scripts.test09
```

New inference can follow a different path, including at temperature 0. Check hashes and settings before comparing runs. The historical E0 batch was reconstructed from older records under different conditions; its 15/20 and this batch's 18/20 do not isolate a causal prompt improvement.

All 20 raw `events.jsonl`, traces, results, evaluation files and HTTP request metadata are retained. The 20 runtime snapshots were byte-identical and are stored once in [source/agent_trace](source/agent_trace); [archive.json](archive.json) maps the original snapshot paths and records copied-file hashes. Original local paths remain provenance only. Rebuildable HTML is omitted. [integrity.json](integrity.json) covers the archived files. Review decisions and their assertion checks are preserved in [build_evidence_review.py](build_evidence_review.py); this is a study artifact, not a runtime mode or a semantic verifier.

[Development plan](../../docs/qa-development.md) · [Historical prompt changes](../../docs/prompt-experiments.md) · [Separate bounded-refinement experiment](../refinement/README.md)

[Checkpoint validation](validation.md) records the test results, including the unresolved full-suite BM25 timing failure, and the offline report/package checks.
