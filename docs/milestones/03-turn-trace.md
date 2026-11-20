# M3 — Horizontal trace and evidence inspector

```text
Implement docs/milestones/03-turn-trace.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

Inspect a turn's sequence, overlap, timing and association problems without raw logs. Requires M2. Read shared references; use UI-SPEC as the primary visual contract.

## Visible UI

A horizontal waterfall attached to the selected session/turn, left-to-right time axis, parallel lanes, shared cursor, evidence inspector and **Verify M3**. Input and output lanes are real; future provider/media/state lanes remain absent or visibly unavailable until supported. A vertical event list is optional detail only.

## Build

- Display measured intervals as spans, discrete events as markers and available held states with distinct semantics. Do not label unknown boundary time as model execution.
- Select a span/marker to show source, direction, identifiers, timing basis, outcome and uncertainty. Raw payloads are optional sanitized detail.
- Correlate inputs, response chunks and interruptions by identifiers. Retain unassigned/robot-wide records on a separate session track rather than the latest turn.
- Use collector elapsed time within a run; distinguish source clocks, reconnects, equal timestamps and sequence. Render late/out-of-order events without rewriting unrelated historical turns.
- Add a keyboard-accessible cursor and readable narrow-screen layout. Plan media synchronization against this cursor without implementing media playback yet.
- Persist enough evidence for traces to reopen after Compose recreation. Display missing spans, incomplete turns and capture gaps.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Run two overlapping turns with an interruption | Separate parallel spans and interruption on the correct output |
| Fixture | Select a bar; move cursor | Correct evidence details and selected time |
| Fixture | Run missing/late/conflicting-ID events | Stable ordering and explicit gaps/unassigned records |
| Fixture | Run unrelated clocks or reconnect | No fabricated cross-clock duration |
| Robot | Capture two close turns and an interruption | Inspect actual events and supported interruption evidence |

Automate association, ordering and duration rules. Exercise span selection, cursor/keyboard operation, narrow layout and reloaded traces in Compose.

## Release gate

Available evidence is correctly assigned or visibly unassigned. Overlap is readable on one horizontal time axis. Timings disclose their basis; prior session reload still works. Record real-robot coverage separately.

## Scope boundary

No provider internals, audio/video players, inferred missing execution or new robot command controls.

## Delivery record

- Implementation: Not started
- Changed paths / run commands: Pending
- Versions / clock/association rules: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / limitations: Pending
- Next action: Implement M3 after M2; then M4A, or M6 early for robot-state discovery.
