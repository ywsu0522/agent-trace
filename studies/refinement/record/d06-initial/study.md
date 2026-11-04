# Bounded document refinement

Retrospective diagnostic; not an E5 benchmark.

| Condition | Answer alias match | Fresh calls | Extra reads |
|---|---|---:|---:|
| archived_baseline | False | 0 | 0 |
| review_only | False | 1 | 0 |
| continue_then_review | True | 1 | 1 |

## archived_baseline

Version 1 of the GridLens API will be shut down on **2027-08-25**.

This date is confirmed in the "GridLens Release Notes, 2025 to 2026" document (ID: `gridlens-release-notes`), which states under the GridLens 4.10 release section that requests to API version 1 paths now return a warning header stating the shutdown date. The document also notes in the GridLens 4.8 release that this shutdown date is stated in the API specification, and the last update to the release notes is dated 2026-08-25, aligning with the planned release cycle ending in August 2027.

## review_only

{'type': 'RuntimeError', 'message': 'Ollama HTTP 500: {"error":"llama-server process has terminated: exit status 0xc0000409: The system detected an overrun of a stack-based buffer in this application. This overrun could potentially allow a malicious user to gain control of this application.: CUDA error: shared object initialization failed\\nCUDA error"}. Check `ollama list` and --model.'}

## continue_then_review

Version 1 of the GridLens API will be shut down on **2026-12-31**.

The draft answer incorrectly cited **2027-08-25** as the shutdown date. The evidence confirms that:
1.  The "GridLens Release Notes, 2025 to 2026" (ID: `gridlens-release-notes`) states in the GridLens 4.10 release section that requests to API version 1 paths return a warning header stating the shutdown date [1](file://gridlens-release-notes#L39).
2.  The "GridLens Ingestion API Specification" (ID: `gridlens-api-spec`) explicitly states in section 10.3 that "API version 1 will be shut down on 2026-12-31" [2](file://gridlens-api-spec#L97).
3.  The draft's reference to the shutdown date being stated in the API specification aligns with this finding, but the specific date provided in the draft was incorrect.

**Supporting Evidence:**
*   **ID: `gridlens-release-notes`**, Line 39: "Note for Customer Success: requests to API version 1 paths now return a warning header that states the shutdown date."
*   **ID: `gridlens-api-spec`**, Line 97-98: "API version 1 will be shut down on 2026-12-31. After that date, requests to `/v1` paths return status 410."

## Limits

- Archived baseline is reused, not rerun; this is not an E5 benchmark.
- Both treatments use one additional model call; the baseline cost is shared.
- All variants are retained; gold never chooses which answer to return.
- Token estimates use ceil(characters/4), not the backend tokenizer.
- Reading a reference line or naming a document is not proof of semantic support.
