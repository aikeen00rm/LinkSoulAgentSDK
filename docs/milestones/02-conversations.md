# M2 — Saved conversation review

```text
Implement docs/milestones/02-conversations.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

Find a session, inspect input/reply turns and reopen them after a restart. Requires the M1 foundation. Read shared references and SDK notes for response/history integration. Preserve the connection screen and its diagnostic behavior.

## Visible UI

Session list, turn selector, input/output text with source labels, incomplete/failed/unassigned indicators, storage health and **Verify M2**. Provide a clear route back to M1. A missing provider or reply has a readable reason.

## Build

- Introduce versioned SQLite schema/migrations for sessions, turns, normalized events and evidence references, stored in the Compose volume.
- Define session/reconnect boundaries; preserve multiple stream chunks sharing an event ID. Reconstruct text in order and deduplicate repeated history snapshots without discarding valid chunks.
- Preserve ambiguous/unassigned evidence and interrupted/incomplete turns. Separate fixture and robot data in queries and UI.
- Add one minimal real text reply provider or verify an existing response path. Keep the isolated M1 connection-test behavior explicit. Detailed provider spans belong to M5; provider configuration errors are visible now.
- Record outgoing response calls with actual sending/acceptance semantics, not assumed robot playback. Follow verified response ordering.
- Provide visual save/reopen verification, bounded text/session retention and backup/migration/rollback instructions. Conversation bodies belong in the database, not diagnostic logs.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Save three distinct turns, restart/reopen | Correct inputs/replies and stable associations |
| Fixture | Replay history snapshots and interleaved chunks | No duplicate history or lost legitimate output |
| Fixture | Interrupt a turn or disable provider | Incomplete/failed reply with explanation, not invented success |
| Fixture | Exercise a write failure | Save failure shown while UI remains usable |
| Robot | Complete three short interactions, recreate/reopen | Actual input and outgoing reply text retained correctly |

Automate persistence, migrations, chunk reconstruction, deduplication and identity isolation. Exercise the session UI with passing and failure examples in Compose.

## Release gate

Captured turns survive recreation without loss, duplication or cross-turn mixing; failed saves are visible. Hardware acceptance needs actual input/reply evidence, not only M1's inference-unavailable response. Physical playback remains separate.

## Scope boundary

No media players or detailed waterfall. Application-typed input, if needed for testing, is explicitly application-originated and does not prove robot capture.

## Delivery record

- Implementation: Ready for verification (0.2.0); hardware acceptance Pending.
- Changed paths: new conversations/recorder/provider modules, conversation UI, M2 tests; app/service/robot/config, shared UI, version/lock, Compose/environment and documentation updated.
- Run commands / migration: `uv lock --offline`, `.venv/bin/pytest -q`, `docker compose config --quiet`, `docker compose build`, `STUDIO_PORT=8001 docker compose up -d --force-recreate --wait`. M1 without SQLite migrates to schema 1; existing reports/logs preserved. Backup/rollback in deployment instructions.
- Versions / provider: Studio 0.2.0, Python 3.14.7, SDK 1.5.0a1, SQLite 3.46.1 in Linux arm64 image. Optional Ollama text provider implemented; HTTP contract tested with isolated server, live model pending.
- Automated + fixture UI checks: Passed; distinct/repeated/interleaved text, history, isolation, interruption/provider/storage failures and restart checks. See validation record for final test count and coverage.
- Compose checks: Passed build/health, M1 upgrade preservation and same-volume recreation/reopen; stopped pre-upgrade backup copied. Separate-volume restore not run.
- Real-robot checks: Not run; agent/provider/firmware/access setup unavailable.
- Evidence / limitations: [M2 validation](../verification/m2-2026-11-20.md). Fixture never satisfies hardware gate. SDK call return does not establish acceptance/playback. Reconnect history without unique current-session identity stays unassigned.
- Next action: configure isolated ASR-text robot agent and reachable Ollama model; finish M1 hardware check, capture three M2 real input/replies and verify after recreation. M3 may use fixture-ready storage meanwhile.
