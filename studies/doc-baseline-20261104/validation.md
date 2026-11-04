# Progress validation — 2026-11-05

This checkpoint preserves a completed experiment and its limitations. It does not claim that the agent satisfies every acceptance criterion.

| Check | Result |
|---|---|
| Full published test suite | 220 passed, 1 failed: existing BM25 query timing check |
| BM25 suite in isolation | 18 passed |
| Current configuration dry-run | Passed; prompt hash matches this baseline |
| Offline reconstruction of archived d06 | Passed; source hash, question, final answer, call counts and session status match |
| Study integrity manifests | All archived files verified |
| Presentation Markdown links | 166 local targets checked before adding this validation page |
| Offline wheel build and isolated installed-wheel dry-run | Passed; single current prompt and both new studies are included |
| New model inference during this validation | 0 calls |

## Tests and the unresolved timing check

The full run used the repository virtual environment:

```sh
python -m pytest tests --ignore=tests/test_legacy_profile.py -q --basetemp=runs/precommit-20261105-tests-01
python -m pytest tests/test_bm25.py -o addopts='' -q
```

`test_legacy_profile.py` is an unpublished workstation-only test. The temporary directory was a new path within the workspace because the sandbox's default pytest temp directory was not writable.

The full run completed 221 cases. `tests/test_bm25.py::test_archive_query_time` measured **26.7 ms** against its unchanged **20 ms** mean-query limit. The BM25 implementation and this test are unchanged from commit `21a42df`. A subsequent isolated run passed all 18 BM25 tests; it did not print a passing mean latency. The different outcomes indicate sensitivity to execution conditions and do not establish that the full-suite performance issue is resolved.

[Full test output](validation/full-suite.log) · [Isolated BM25 output](validation/bm25-isolated.log)

## Artifact and installation checks

All 20 raw event files match their trace checksums, and the batch contains 78 main-model HTTP requests with corresponding responses and no auxiliary calls. Every copied file matches its source in the completed run. All 20 per-run runtime snapshots matched the shared archived snapshot, verified file by file. Original answers, automatic scores and recorded configurations remain unchanged.

The current configuration's historical note was updated after the run to remove the stale “no full 20-question score” statement. This is descriptive metadata only; the recorded profile retains its original text. The system prompt and runtime code match the frozen baseline.

The wheel was built with `uv build --wheel --offline`, then extracted and checked in Python isolated mode (`-I`) from outside the repository root. The packaged CLI's d01 dry-run resolved its bundled assets, used the expected prompt hash and found both new study directories. No generated wheel, installed copy, cache or HTML report is published.
