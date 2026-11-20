# Project instructions

Build a visual recorder and debugger for one user-owned AGIBOT A3 Ultra with Python LinkSoul AgentSDK. The approved product has media previews, a horizontal tracing waterfall, robot-state evidence and guided visual verification. Docker Compose is the primary deployment.

## Start a milestone chat

1. Read `docs/STATUS.md` for actual implementation and unresolved dependencies.
2. Read only the requested contract under `docs/milestones/`. Use its README to resolve the milestone ID; load other milestone contracts only for a dependency.
3. Read `docs/ARCHITECTURE.md`, `docs/UI-SPEC.md`, `docs/VERIFICATION.md` and `docs/DEPLOYMENT.md` before implementing. For SDK, media or robot-state integration, read `docs/SDK-NOTES.md` and verify relevant official APIs against the package installed for this build.
4. Inspect the actual checkout and preserve cumulative behavior/data. Implement the requested milestone, not subsequent stages. If implementation dependencies are missing, report the exact dependency and complete independent work that is valid without it.

The repository was reset on 2026-11-20. Initial status is documentation only. Previous implementation and validation do not count as evidence for this build. This is a historical reset, not an instruction to reset again in future chats.

## Product rules

- Every milestone delivers a usable UI, guided verification, automatically saved sanitized diagnostics and a Compose release. Routine troubleshooting must not require raw logs.
- Label `fixture` versus `robot` on screens, recordings and verification reports. Simulated checks never satisfy hardware gates.
- Label evidence as SDK captured, application measured, robot reported, inferred or unavailable. Sending, acceptance and execution completion are distinct.
- Correlate by available identifiers. Ambiguous evidence stays unassigned; missing reports stay unknown. Timing proximity is not proof of a turn association.
- Keep credentials server-side. Store conversation/media in designated stores, outside diagnostic logs. Bound storage and work queues; surface capture loss and storage failures visually.
- Playback reviews saved evidence locally. Robot commands require a separate explicit operation; verification controls must not silently initiate motion.
- Respect one passive callback and one SDK-owning process. Verify callback configuration before changing the active interaction path.

## Finish a milestone chat

1. Run relevant automated checks, exercise the UI in passing and failure states, and perform Compose startup/recreation checks where available. Mark unperformed checks pending with reasons.
2. Save a scoped validation record under `docs/verification/` with actual build/package versions, fixture/hardware separation, steps and evidence references. Keep runtime data/secrets out of Git.
3. Update the milestone delivery record and `docs/STATUS.md`: changed paths, commands, results, limitations and next concrete action. Add durable decisions to architecture/SDK notes; avoid chat transcripts.
4. Update README/deployment instructions to match commands that now exist. Preserve saved evidence across later releases and document migrations/rollback.
5. Claim acceptance only when the milestone's gate has evidence. Implementation may be ready for hardware verification while acceptance remains pending.
