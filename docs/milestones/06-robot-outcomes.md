# M6 — Robot states and execution evidence

```text
Implement docs/milestones/06-robot-outcomes.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

See reported movement, manipulation, action and speech state, distinguishing dispatch from actual reported outcome. Requires M3 and published robot modules for hardware acceptance. M4A is needed only for recorded-audio comparison; M5/video are not blockers. Read shared references and verify official state schemas against actual received evidence.

## Visible UI

Module-coverage panel, robot-state summary at cursor, horizontal navigation/manipulation/action/speech lanes, task lifecycle inspector and **Verify M6**. Every state shows source, age, association and uncertainty. Unavailable joint telemetry and GPS remain explicit.

## Build

- Inventory actual `tts_status`, `locomotion_status`, `robot_pose`, `manipulation` and `action_status` publication; include semantic location/path only where useful and available. Record firmware/schema coverage.
- Normalize state strings/objects/arrays without losing original supported evidence. Support concurrent tasks and duplicate/late/out-of-order reports.
- Correlate operations to state/task/result evidence using actual IDs. Keep robot-wide/unrelated state on the session track; time proximity alone never attaches it to a conversation.
- Separate attempted/sent, accepted when observable, running, completed, failed, interrupted and unconfirmed. Missing final evidence/timeout is not success or proof of execution failure.
- Display held state bands with freshness and gaps. Navigation state/pose may describe movement; manipulation `is_on`/mode only describe capability/configuration. Arm joint angles and grasp success require their own evidence.
- Distinguish map-frame/semantic location from latitude/longitude. Preserve state history across Compose recreation and connect to the shared cursor.
- Verification observes separately scoped operator interactions. Normal monitor/replay never initiates motion.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Run matching playback/task completion | Completed only after matching final report |
| Fixture | Run interrupted/failed/missing-final scenarios | Distinct outcomes; absent confirmation remains unknown |
| Fixture | Manipulation enabled with failed/missing action | No inferred moving arm or successful grasp |
| Fixture | Late/unrelated reports and concurrent tasks | Correct identity, freshness and unassigned evidence |
| Robot | Speak and interrupt playback | Actual published speech reports and coverage shown |
| Robot | Separately scoped supported movement/action | Real available task/state evidence, no blanket capability claim |

Automate lifecycle/correlation/staleness rules. Visually inspect reported and missing-telemetry scenarios; recreate and reopen recorded state traces.

## Release gate

Supported robot modules display with correctly associated evidence, and missing confirmation stays unconfirmed. Record exact observed A3 Ultra capabilities and limits. A pass for speech does not verify movement, manipulation or all documented modules; unsupported requested coverage remains a limitation.

## Scope boundary

Independent physical verification, joint-level control/telemetry without a supported source, arbitrary robot commands, teleop and skill-authoring consoles.

## Delivery record

- Implementation: Not started
- Changed paths / run commands / schema: Pending
- Versions / firmware / observed module coverage: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / correlation limits / unsupported capabilities: Pending
- Next action: Implement M6 after M3 when state coverage is prioritized, or after media/processing releases. Record remaining unsupported scope explicitly.
