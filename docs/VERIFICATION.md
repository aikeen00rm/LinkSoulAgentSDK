# Verification and milestone acceptance

## Fast operator workflow

Every release has a visible **Verify this milestone** panel, a short passing path and at least one meaningful failure path. Aim for a few minutes of operator interaction once prerequisites are configured; do not promise a duration for hardware setup or long recordings.

Each check shows:

- Mode, selected agent/device association, build/SDK versions and prerequisites.
- What the operator does and the expected visible result.
- What evidence was actually observed, with timestamps and identifiers.
- Passed / Failed / Pending / Unsupported, plus a plain-language reason and recovery action.
- Report persistence state and a way to reopen/download the saved result.

Fixture controls exercise actual adapters/collectors/storage/UI. Hardware checks require real callbacks/media/reports; demo data never substitutes for them. Starting verification never silently triggers robot motion. Playback checks replay local evidence only.

## Shared checks

Each milestone runs its relevant automated tests, desktop/narrow-screen UI checks, keyboard operation and one passing/failure visual scenario. Exercise actual media players when introduced; a waveform or illustration alone does not demonstrate playback/capture.

Use the [deployment gate](DEPLOYMENT.md#every-releases-deployment-gate) for Compose build, health, recreation and persistence. Preserve previous data and behavior across cumulative releases. Test only relevant behavior and affected regressions; record what was run, not an aspirational checklist of passes.

Keep diagnostic logs automatically saved, sanitized and rotated. Make storage/queue/capture failures visible. If storage itself is unavailable, show that the report cannot be saved; never claim durable success from memory alone.

## Runtime check report

M1 implements an atomic report store, separated by fixture/robot mode. Later stages add evidence without losing old reports. Each report contains a schema version, report ID, milestone/scenario, start/end UTC, mode, build/package versions, selected agent and physical association status, steps/expected/observed outcomes, evidence record references, result, limitations and persistence status.

Keep secrets, full conversations and media out of default diagnostic reports/exports. Recordings and text belong in their designated stores, linked by internal IDs. Runtime reports are ignored by Git; curated sanitized summaries may be included in `docs/verification/`.

## Acceptance states

- **Implementation ready:** feature and fixture/UI checks work; outstanding hardware/container checks are explicitly pending.
- **Accepted for verified scope:** the contract's release gate has evidence, including its required real-robot path. State the exact supported input/media/module coverage.
- **Unsupported:** actual capability/configuration evidence explains why a feature cannot be provided; it is not equivalent to a pass. An unsupported part of the requested scope remains a limitation unless the user changes scope.

No old build, documentation example, mockup, method call or timeout alone proves a robot action completed. Separate sending, acceptance and execution reports.

## Record for the next chat

Create `docs/verification/<milestone>-<date>.md` with:

```text
Build and environment:
Changed paths:
Commands/checks actually performed:
Fixture automated/UI evidence:
Compose build/health/recreation evidence:
Real-robot evidence and observed capabilities:
Unperformed checks and reasons:
Known limitations / migration / recovery:
Next concrete action:
```

Update the milestone delivery record and status table. Record durable choices in architecture/SDK notes and exact tested deployment commands in README. This is the handoff to a clean chat, not a transcript of the work.
