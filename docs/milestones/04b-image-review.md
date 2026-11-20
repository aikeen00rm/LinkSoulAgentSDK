# M4B — Captured images and frame inspection

```text
Implement docs/milestones/04b-image-review.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

See actual captured images beside the trace and reopen them after restart. Requires M4A and a supported camera/image source for hardware acceptance. Read shared references and verify SDK frame hooks/formats against the installed package.

## Visible UI

Timestamped thumbnail strip, enlarged image preview, frame/source details, trace selection and **Verify M4B**. Distinguish still images from video frames and robot capture from application uploads. Sparse stills are not presented as continuous footage.

## Build

- Verify image payload availability or decode a still from an actual supported video source, respecting keyframes/codec prerequisites. Use the correct flags for each SDK hook.
- Retain media reference, encoding/dimensions, source timestamp, collector time/sequence, run/session and available turn IDs. Keep ambiguous frames unassigned.
- Persist original supported images and bounded thumbnails. Publish files atomically, validate media identifiers and handle missing/orphaned files.
- Link selected timestamps/images to the horizontal trace cursor. A frame near a time does not establish causal turn association.
- Bound decode dimensions, sampling, queues, storage and retention; decode/resize outside callbacks. Show dropped frames, capture-disabled, camera-unavailable, corrupt/unsupported encoding and write failures.
- Package dependencies inside Compose. Capture/review does not require image understanding; add a minimal vision provider only if image-based replies are explicitly included, with honest coverage labels.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Select distinct known images at known times | Correct preview, source and timestamp |
| Fixture | Inspect overlapping turns/unassigned frame | No automatic attachment to latest turn |
| Fixture | Use corrupt/oversized/missing image | Readable error; other evidence stays usable |
| Compose | Recreate and reopen images | Correct persistent files/references |
| Robot | Capture a recognizable scene with the A3 Ultra | Actual scene visible with format/source/timing evidence |

Automate lookup/association, limits, decode/storage failures and retention. Inspect real image fixtures and hardware images separately; illustrations cannot satisfy capture acceptance.

## Release gate

Actual captured images render after recreation and remain correctly associated. Missing frames and uncertain time alignment are explicit. Hardware format/source support is recorded.

## Scope boundary

Continuous video, scene inference by default, arm pose reconstruction and arbitrary image injection into the robot.

## Delivery record

- Implementation: Not started
- Changed paths / run commands / migrations: Pending
- Versions / image source / codecs: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / limitations: Pending
- Next action: Implement M4B after M4A; then M4C.
