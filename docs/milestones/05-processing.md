# M5 — Application processing diagnostics

```text
Implement docs/milestones/05-processing.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

Identify which application service delayed/failed a turn and whether output was produced. Requires M3 + M4A and actual application provider calls. Images/video are not blockers. Read shared references; inspect the implemented provider boundary rather than assuming hidden platform access.

## Visible UI

ASR/model/TTS and any existing tool/retrieval spans in the same horizontal trace, selectable provider details, retry/cancellation indicators, readable incident guidance and **Verify M5**. Unused/unobservable services are labeled accordingly.

## Build

- Instrument providers already integrated for working conversations. Record parent/turn association, monotonic boundaries, first output when observable, safe provider/configuration identifiers, attempt and outcome.
- Preserve streaming overlap, partial output, retries, cancellation, timeout and final failure as distinct evidence. Avoid creating spans for work that never started.
- Explain the affected stage and recovery action without requiring raw request/response dumps. Keep secrets/full bodies outside diagnostics.
- Add deterministic delayed/error/cancelled fixture services through the actual instrumentation path.
- Persist spans and incident references in the existing volume; replay after recreation. Link to available text/audio/images/video without requiring unimplemented media.
- Retain the working pipeline and earlier UI. Model/provider integration is not delayed until M5; this release adds observability.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Run a known model delay | Delay appears on correct span within documented tolerance |
| Fixture | Run provider timeout/error | Affected turn/stage fails; unstarted TTS stays unstarted |
| Fixture | Run streaming/retry/interruption | Correct overlapping attempts and cancellation links |
| Compose | Recreate and reopen failed turn | Saved span/error explanation remains |
| Robot | Interact through an application-controlled provider | Actual spans align with captured input/output evidence |

Automate timing, attribution, parent/turn isolation and cancellation. Visually select spans and inspect both passing and failed scenarios.

## Release gate

A known delay and controlled failure are attributed to the correct service and turn. Actual robot interactions expose the application-controlled boundaries used. Unobserved platform internals are not presented as measured work.

## Scope boundary

Automatic provider replacement, new retrieval/tools solely for tracing, AGIBOT hidden internals and unrelated analytics dashboards.

## Delivery record

- Implementation: Not started
- Changed paths / run commands / schema: Pending
- Versions / provider coverage: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / timing tolerance / limitations: Pending
- Next action: Implement M5 after M4A; complete M6 if outstanding.
