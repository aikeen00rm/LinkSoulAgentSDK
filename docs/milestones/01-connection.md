# M1 — Connection console and Compose foundation

```text
Implement docs/milestones/01-connection.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

From this documentation-only checkout, create a runnable console for one A3 Ultra. No implementation dependency. Read the shared references in [the roadmap](README.md#required-shared-references) plus SDK notes. Verify real Docker/package/hardware prerequisites; old project results do not apply.

## Visible UI

Connection screen with fixture/robot badge, versions, gateway status, robot presence, selected agent/physical-association status, last-input freshness, capture coverage, readable incident guidance and **Verify M1**. Include fixture controls and a step-by-step robot setup checklist. Later media/trace features are not represented as implemented.

## Build

- Create Python package, web service, real/fixture adapters and bounded normalized collector. Use one SDK owner and lifecycle-managed registration/initialize/release.
- Lock dependencies and provide Dockerfile/Compose, fixture default, health endpoint, server-side configuration, persistent volume and tested README commands.
- Select the simplest supported isolated callback, preferably ASR text. Capture input-arrival metadata. An explicit inference-unavailable reply is acceptable for this connection test, labeled accordingly; it does not establish a conversation pipeline.
- Show connectivity, online presence and input freshness independently. Reconnect invalidates prior freshness; unrelated agents cannot silently become the target.
- Persist sanitized rotating app/SDK diagnostics and atomic mode-separated check reports. Surface storage, authentication/configuration, queue and adapter errors.
- Verify authentication/TLS and logging against the installed SDK. Record exact package/runtime versions and known compatibility limits.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Run reconnect + fresh input | Connection/presence/freshness change; saved Passed · fixture report |
| Fixture | Run reconnect without new input | Waiting/stale input; prior success cannot pass the check |
| Fixture | Run configuration/storage failure scenarios | Readable failure and recovery; no false report-save claim |
| Robot | Start check, connect, speak, disconnect/reconnect, speak again | Real selected-agent callbacks and fresh post-reconnect input |
| Compose | Recreate with the same volume | Prior reports/diagnostics reopen; live state is freshly established |

Automate lifecycle, filtering/correlation, freshness, redaction, rotation and report durability. Exercise desktop/narrow UI and keyboard controls in success/failure states.

## Release gate

Compose build/start/health and persistence pass. The UI receives genuine input from the associated A3 Ultra after reconnect and reports failures honestly. Fixture-ready code with missing hardware access is ready for verification, not accepted.

## Scope boundary

No conversation database, media recording, provider tracing, motion controls or invented completed replies. Inventory media/state support only as a future dependency.

## Delivery record

- Implementation: Ready for verification; fixture-first scope completed on 2026-11-20.
- Changed paths: Python package and web assets, `tests/test_m1.py`, `pyproject.toml`, `uv.lock`, Dockerfile, Compose, environment example, README and shared handoff docs.
- Exact build/run: `uv sync --locked`; `.venv/bin/pytest -q`; `STUDIO_PORT=8001 docker compose up --build -d`; `STUDIO_PORT=8001 docker compose up -d --force-recreate`.
- Versions: Studio 0.1.0, Python 3.14.7, SDK 1.5.0a1, uv 0.12.9, Docker 29.6.2, Compose 5.3.1. Linux arm64 container.
- Automated checks: 16 passed; one dependency deprecation warning. Includes identity filtering, missing/replayed input IDs, stale input, queue loss, SDK lifecycle/TLS configuration, metadata privacy, rotation, ownership, failed report writes and restart durability.
- Fixture UI: recovery, missing input, invalid configuration, isolated storage failure, keyboard activation and desktop/narrow layout exercised.
- Compose: build/start/health passed; five report hashes unchanged after recreation, diagnostics retained and appended; fresh live state reset as intended.
- Real robot: Not run. User has not configured developer application or isolated agent and requested fixture-first verification.
- Evidence: [dated checks and limitations](../verification/m1-2026-11-20.md), [UI screenshot](../verification/m1-fixture.png). Runtime reports remain in the named volume.
- Observed capabilities: fixture metadata collection and installed-SDK compatibility only; no hardware capability demonstrated. No text/media recording, provider pipeline or motion control.
- Next action: configure the isolated robot test and run the hardware gate; M2 may proceed with fixtures while this gate stays pending.
