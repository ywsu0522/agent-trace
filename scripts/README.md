# HW1 pipeline evaluation

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
