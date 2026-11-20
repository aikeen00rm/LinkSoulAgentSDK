# LinkSoul Studio — A3 Ultra visual recorder

A fresh project plan for one AGIBOT A3 Ultra using Python LinkSoul AgentSDK. The application will show captured input/output, image and video previews, a horizontal trace, robot-reported states and fast visual checks.

**Current state: M2 saved-conversation review is ready for hardware verification.** Sessions, ordered input/reply text, separate history evidence, failure states and restart verification are implemented. Fixture tests and Compose recreation passed; real robot/model checks remain pending.

Open [conversation review](http://127.0.0.1:8001/conversations) or [M1 connection](http://127.0.0.1:8001/). See [M2 validation](docs/verification/m2-2026-11-20.md).

## Build one milestone per chat

Open a new chat in this repository, then paste the prompt for the milestone you want. Each contract contains its UI, scope, quick verification, failure cases, acceptance gate and delivery record.

| Release | What becomes usable | Paste into a new chat |
| --- | --- | --- |
| M1 | Connection console + Docker Compose | `Implement docs/milestones/01-connection.md. Follow AGENTS.md and update the handoff when finished.` |
| M2 | Saved text inputs and replies | `Implement docs/milestones/02-conversations.md. Follow AGENTS.md and update the handoff when finished.` |
| M3 | Horizontal trace + evidence inspector | `Implement docs/milestones/03-turn-trace.md. Follow AGENTS.md and update the handoff when finished.` |
| M4A | Captured audio and playback | `Implement docs/milestones/04-audio-review.md. Follow AGENTS.md and update the handoff when finished.` |
| M4B | Captured images and frame inspection | `Implement docs/milestones/04b-image-review.md. Follow AGENTS.md and update the handoff when finished.` |
| M4C | Saved video synchronized with the trace | `Implement docs/milestones/04c-video-review.md. Follow AGENTS.md and update the handoff when finished.` |
| M5 | Application processing diagnostics | `Implement docs/milestones/05-processing.md. Follow AGENTS.md and update the handoff when finished.` |
| M6 | Robot movement, manipulation and action reports | `Implement docs/milestones/06-robot-outcomes.md. Follow AGENTS.md and update the handoff when finished.` |

M1 and M2 are implemented for fixture review; hardware acceptance remains pending. Follow the table by default. After M3, M6 can be brought forward to verify robot-state coverage; it does not need video. M5 needs M4A but not images/video. Read the [roadmap](docs/milestones/README.md) for dependency details.

Each chat must read the current status, build only its milestone, preserve earlier releases, and leave an updated delivery record. A new chat uses the files, not assumptions from previous conversations.

## Intended UI

- Connection, recording and capture-coverage indicators distinguish fixture data from your robot.
- Session/turn browser shows input text and outgoing responses.
- Media preview shows actual images/video when captured, with audio playback.
- A **horizontal waterfall** aligns input, processing, output and robot reports on one time axis. Select a bar to inspect evidence; move the cursor to review media and reported state.
- Every milestone includes **Verify this milestone** with visible steps, expected results, recovery guidance and saved reports.

See [UI specification](docs/UI-SPEC.md). Concept labels describe intended behavior, not features already implemented.

## Docker Compose

No credentials are needed for fixture mode. With Docker running:

```sh
STUDIO_PORT=8001 docker compose up -d --build
docker compose ps
```

Open [localhost:8001](http://127.0.0.1:8001). Port 8000 is the default; 8001 was tested because 8000 is occupied on this host. Use the same port override whenever recreating the service, or put `STUDIO_PORT=8001` in a local `.env` copied from `.env.example`.

Click **Run reconnect + fresh input**: expect seven completed steps and **Passed · fixture**. Try each failure button: expect **Failed · fixture** and readable guidance. Run recovery again to clear a simulated incident. Saved reports remain downloadable after recreation; current connection evidence resets. The storage scenario tests a deliberately unusable temporary path while saving its failed-check report to healthy persistent storage.

```sh
STUDIO_PORT=8001 docker compose up -d --force-recreate
```

For local development: `uv sync --locked`, then `.venv/bin/pytest -q` and `.venv/bin/uvicorn linksoul_studio.app:app --port 8001`. Use one process; do not enable reload for robot mode. The actual distribution is SDK **1.5.0a1**, not a final 1.5.0 release.

Logs, reports and the M2 conversation database live in the `linksoul-studio-v2-data` volume. Conversation bodies stay out of diagnostics. Media capture is not yet implemented. See [deployment instructions](docs/DEPLOYMENT.md) for setup, storage, backups and future robot verification.

## Project references

- [Actual status and next action](docs/STATUS.md)
- [Milestone roadmap](docs/milestones/README.md)
- [Architecture and evidence model](docs/ARCHITECTURE.md)
- [Visual design](docs/UI-SPEC.md)
- [Fast verification and acceptance](docs/VERIFICATION.md)
- [Docker Compose contract](docs/DEPLOYMENT.md)
- [SDK references and compatibility questions](docs/SDK-NOTES.md)

The owner has an A3 Ultra. Firmware, developer entitlement, region, agent configuration, providers and published media/state capabilities still require verification. Fixtures let UI development proceed while hardware checks remain explicitly pending.

## Saved conversation checks

At `/conversations`, click **Save three fixture turns**, inspect the turn selector, then **Save restart checkpoint**. Recreate with `STUDIO_PORT=8001 docker compose up -d --force-recreate --wait`, select the same session and click **Verify saved session after restart**. A successful reopen produces **Passed · fixture** and an automatically saved report. Test interleaved history, interrupted reply, disabled provider and save failure with the adjacent controls.

M2 supports an optional server-configured Ollama text provider. Set `STUDIO_REPLY_PROVIDER=ollama`, `OLLAMA_URL` and `OLLAMA_MODEL` in `.env`, recreate, and use M2's explicit reply connection after confirming the isolated robot callback configuration. Defaults keep the provider disabled. See [deployment instructions](docs/DEPLOYMENT.md#m2-release-saved-conversations) for limits, setup and rollback. Actual robot input/replies and a live model still need verification.
