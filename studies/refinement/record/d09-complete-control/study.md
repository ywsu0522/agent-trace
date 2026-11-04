# Bounded document refinement

Retrospective diagnostic; not an E5 benchmark.

| Condition | Answer alias match | Fresh calls | Extra reads |
|---|---|---:|---:|
| archived_baseline | True | 0 | 0 |
| review_only | True | 1 | 0 |
| continue_then_review | None | 0 | 0 |

## archived_baseline

The error code that means the sensor mesh link was lost is **E-214**.

According to Section 11.2 of the "EmberOS 3 Firmware Specification" (document ID: `firmware-spec-emberos`), the table lists error codes and their meanings, where E-214 corresponds to "Sensor mesh link lost". Additionally, Section 11.3 confirms that this error is raised by the M4 when a joined sensor has sent no report for 15 minutes.

**Answer:** E-214
**Evidence ID:** firmware-spec-emberos

## review_only

The error code that means the sensor mesh link was lost is **E-214**.

According to Section 11.2 of the "EmberOS 3 Firmware Specification" (document ID: `firmware-spec-emberos`), the table lists error codes and their meanings, where E-214 corresponds to "Sensor mesh link lost". Additionally, Section 11.3 confirms that this error is raised by the M4 when a joined sensor has sent no report for 15 minutes.

**Answer:** E-214
**Evidence ID:** firmware-spec-emberos

## continue_then_review

no_unread_continuation

## Limits

- Archived baseline is reused, not rerun; this is not an E5 benchmark.
- Both treatments use one additional model call; the baseline cost is shared.
- All variants are retained; gold never chooses which answer to return.
- Token estimates use ceil(characters/4), not the backend tokenizer.
- Reading a reference line or naming a document is not proof of semantic support.
