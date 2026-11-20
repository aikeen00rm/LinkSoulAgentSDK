# Docker Compose deployment contract

M1 provides a runnable fixture console. Build/start/health and same-volume recreation were verified on Docker Desktop, macOS arm64. See the dated validation record. Real-robot setup is pending.

## Target host and services

Run on the operator's external computer/server with Docker Engine/Desktop, Compose and gateway connectivity. Installation onto the robot is not assumed. Verify host OS/architecture, Python/package compatibility and Docker availability during M1.

One `studio` service contains the Python web app, SDK adapter and background capture work. Use one SDK-owning process without reload. SQLite/filesystem storage avoids additional services initially. Package any later media decoders/muxers in the image with recorded versions; startup must not download/install dependencies.

M1 supplies `Dockerfile`, `compose.yaml`, locked Python dependencies, `.env.example`, ignore rules, health checks, an unprivileged runtime user and reproducible build instructions. Preserve loopback binding at `127.0.0.1:8000` by default. Remote access needs an authenticated protected route, such as a configured reverse proxy or tunnel; it is a separate deployment decision.

## Intended operator commands

Use `STUDIO_PORT=8001` before creation/recreation commands on this host (8000 is occupied). Default port remains 8000:

```sh
docker compose up -d --build
docker compose ps
docker compose stop
docker compose start
docker compose up -d --build --force-recreate
docker compose down
```

Document browser URL, fixture setup, robot setup and provider configuration in README. Applying environment changes requires container recreation rather than a plain restart. Diagnose normal issues in the UI; container logs remain support material.

## Persistent data and fresh-start boundary

Mount one named volume at `/data`. Use a fresh volume name, such as `linksoul-studio-v2-data`, rather than silently importing external volumes from the discarded project. The reset did not remove external Docker containers/volumes. Check for old containers/port conflicts before starting; do not delete external resources automatically.

The volume contains diagnostics, verification reports, SQLite and media as each milestone introduces them. Container recreation and ordinary `docker compose down` must preserve it. Document that `down -v` deletes data and is not part of normal updates.

Support a bind mount only with documented ownership/write-permission handling. Never solve permissions by making secrets/recordings world-readable/writable. Prevent two processes from owning the same data/SDK connection.

## Configuration and secrets

- Default fixture operation needs no robot/provider credentials.
- Keep local `.env` and credentials out of Git and browser responses. M1 defines validated variable names and documents them in `.env.example`; later releases extend them for providers/capture/retention.
- Robot mode requires the actual regional gateway, application credentials and agent association. Discover or filter the selected agent using the verified SDK contract; do not assume a platform agent ID proves the physical serial number.
- Configuration/storage/adapter errors leave a readable UI wherever possible. Health separates web/storage readiness from robot connectivity; an offline robot is not automatically a dead web service.
- Bound Docker output and application/SDK diagnostic rotation independently. Set explicit media retention and work limits when capture is introduced.

## Every release's deployment gate

1. Validate Compose without printing secrets; build the locked image and record actual build/Python/SDK/codec versions and architecture.
2. Start fixture mode and verify health, UI success/failure scenarios and saved reports.
3. Stop/recreate with the same volume; reopen earlier evidence and verify writes/rotation still work.
4. For later releases, test migrations against prior-release data and retain previous screen behavior.
5. Run robot-specific checks only with configured access; record them separately. Missing engine/access leaves the relevant checks pending.

Before upgrades, stop the service and back up the entire volume plus separately protected configuration. Keep the previous image. Rollback either uses a verified compatible schema or restores the complete pre-upgrade backup; never assume an older build can read a newer database. M1 must document an actual backup/restore procedure for its chosen volume setup.

## M1 operating details

`studio` runs as UID 10001, owns `/data`, and serves only loopback. The named volume is `linksoul-studio-v2-data`; no discarded-project volume is imported. An exclusive filesystem lock prevents two owners of this data directory. Bind mounts are not supplied in this release; if adding one, provision it for UID 10001 first. The web interface has no login and must not be exposed directly to a network.

`/health` measures configuration, storage and event-loss readiness, independently of robot connectivity. Logs are `/data/logs/app.jsonl` and `sdk.jsonl`: each defaults to 1 MiB plus five rotated backups. Docker stdout rotates separately at 10 MiB with three files. Reports are atomic JSON under `/data/verification/{fixture,robot}/`; newest 100 are listed, all remain retained until manually archived. M1 originally had no database/media store; M2 now adds the SQLite store described below.

For robot verification, copy `.env.example` to `.env`, keep it private, select `STUDIO_MODE=robot`, and configure administrator-confirmed regional `wss` gateway, application ID/key/secret and preferably the intended agent ID. Use an isolated ASR-text test agent associated with this A3 Ultra. Recreate, open the setup checklist, start a manual check, Connect, obtain online presence and speak. Disconnect, Connect and speak again; finish and save the check. M1 deliberately attempts an inference-unavailable error response. It does not implement conversation inference. Confirm physical association separately; a platform ID is insufficient. No hardware test was attempted because setup is not yet available.

## Backup and restore procedure

Stop the writer and copy the entire volume; protect `.env` separately. Choose a new backup directory each time:

```sh
docker compose stop studio
docker compose cp studio:/data ./m1-backup
docker compose start studio
```

Before restoring, stop the service and preserve its current data in a separate backup. Copy a complete known-good backup into the stopped container's mounted volume, preserving ownership, then start:

```sh
docker compose stop studio
docker compose cp --archive ./m1-backup/. studio:/data
docker compose start studio
```

Use a clean destination volume for rollback when newer files or schemas exist; copying does not remove extra files. Check storage readiness and download a known report after restore. Backup/restore commands are documented but have not been exercised in this delivery; same-volume container recreation was tested. Do not use `docker compose down -v` for normal updates: it deletes persistent data.

## M2 release: saved conversations

The release image is `linksoul-studio-v2:0.2.0`. Start/recreate and wait for health:

```sh
STUDIO_PORT=8001 docker compose up -d --build --wait
STUDIO_PORT=8001 docker compose up -d --force-recreate --wait
```

Open `/conversations`. Save three fixture turns, inspect all three, save a restart checkpoint, recreate using the second command, reopen the session and click **Verify saved session after restart**. Fixture history/interruption/provider/save-failure controls save sanitized reports automatically. The storage scenario performs a real read-only SQLite write failure in a temporary database; it does not damage the recording database. Real storage failures show unavailable health and prevent a saved-success claim. Review controls never send robot commands.

M2 creates schema 1 in `/data/linksoul.sqlite3`; M1 reports/logs stay in place. The same `linksoul-studio-v2-data` volume persists across recreation. Defaults in `.env.example`: 100 sessions per mode, 200 turns/session, 8,192 characters/text event; 4,000 events/session and 128 MiB database page limit are fixed. New sessions remove the oldest sessions only in their own mode. Queue/capture loss and failed writes are visible. Protect recordings as private data; runtime stores remain outside Git and diagnostics.

For real text replies, install/run an Ollama model separately and configure server-side `.env`:

```dotenv
STUDIO_REPLY_PROVIDER=ollama
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=your-installed-model
```

Use an appropriate reachable provider address for your host; local Python commonly uses `http://127.0.0.1:11434`. Keep Ollama restricted to intended clients. No live provider is bundled or automatically downloaded. Recreate the service after configuration. In robot mode, disconnect any M1 test connection, open M2, confirm the administrator-verified agent uses Asr2LlmCallback, then explicitly **Connect with M2 text replies**. This enables outgoing text on new captured requests. Provider disabled/configuration/timeout failures retain input with a readable failed-reply reason. The normal M1 Connect operation remains connection-test-only. Sending, acceptance and physical playback stay distinct.

Use the stopped-volume backup procedure above with an M2-specific destination, for example `./m2-backup`. A full pre-upgrade backup was copied during M2 verification; do not treat a running SQLite-file copy as a complete backup. For rollback to 0.1.0, retain its image and restore the complete pre-M2 volume into a clean destination volume with UID 10001 ownership, then use the previous Compose/configuration. Schema 1 is not declared supported by older application versions. Preserve the M2 backup separately so recorded sessions can be restored with 0.2.0. Restore into a separate volume has not yet been exercised; same-volume recreation and M1 report preservation passed.
