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

The draft answer is incorrect because it claims the shutdown date is **2027-08-25**, but the provided documents do not contain this specific date.

**Correction:**
The evidence confirms that API version 1 will be shut down on **2026-08-25**.

*   The "GridLens Release Notes, 2025 to 2026" (ID: `gridlens-release-notes`) states in the GridLens 4.10 release section (Released: 2026-08-25) that "requests to API version 1 paths now return a warning header that states the shutdown date."
*   The same document notes in the GridLens 4.8 release section (Released: 2026-02-24) that "the shutdown date for API version 1 is now stated in the API specification."
*   The "GridLens Ingestion API Specification" (ID: `gridlens-api-spec`) does not explicitly list the shutdown date in the provided snippets, but the release notes confirm the date is stated there and aligns with the release cycle ending on **2026-08-25**.

The draft incorrectly inferred a future date of 2027 based on an "August" mention without specific evidence for the year 2027. The document explicitly links the shutdown notice to the release date of August 25, 2026.

**Final Answer:**
Version 1 of the GridLens API will be shut down on **2026-08-25**. This is confirmed by the "GridLens Release Notes, 2025 to 2026" document (ID: `gridlens-release-notes`), which states in

## continue_then_review

Version 1 of the GridLens API will be shut down on **2026-12-31**.

The draft answer incorrectly cited a date of 2027-08-25 based on an assumption about the release cycle. The correct date is explicitly stated in the "GridLens Ingestion API Specification" (ID: `gridlens-api-spec`) under section **10.3**, which reads: "API version 1 will be shut down on 2026-12-31." This information was also confirmed in the "GridLens Release Notes, 2025 to 2026" (ID: `gridlens-release-notes`), where the GridLens 4.8 release notes state that the shutdown date is now stated in the API specification.

**Supporting Evidence:**
*   **Document ID:** `gridlens-api-spec`, Line 103: "API version 1 will be shut down on 2026-12-31."
*   **Document ID:** `gridlens-release-notes`, Line 58: "Note for Customer Success: the shutdown date for API version 1 is now stated in the API specification."

## Limits

- Archived baseline is reused, not rerun; this is not an E5 benchmark.
- Both treatments use one additional model call; the baseline cost is shared.
- All variants are retained; gold never chooses which answer to return.
- Token estimates use ceil(characters/4), not the backend tokenizer.
- Reading a reference line or naming a document is not proof of semantic support.
