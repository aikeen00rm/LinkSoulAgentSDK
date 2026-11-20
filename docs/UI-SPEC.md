# Product UI specification

## Shared application shell

Show LinkSoul Studio, build/SDK version, selected A3 Ultra/agent, fixture/robot mode and capture coverage on every screen. Distinguish gateway connection, robot presence and last-input freshness. Unsupported, stale and unknown states have text labels, not only colors.

Use a restrained desktop interface with readable text, compact panels and neutral surfaces. Support keyboard operation and narrow layouts. Preserve earlier screens as features ship; future screens are absent or explicitly marked not implemented.

## Review screen

The approved review design uses this structure:

```text
LinkSoul Studio       ROBOT or FIXTURE       A3 Ultra / agent / versions
Connection / robot presence / input freshness / capture coverage

Session + turn selector                       Verify this milestone

+----------------------------+--------------------------------------+
| Image / video preview      | Input text and outgoing response     |
| Captured timestamp         | Reported state at the selected time  |
| Audio / video playback     | Navigation / action / manipulation   |
+----------------------------+--------------------------------------+

Horizontal trace                    0s    2s    4s    6s    8s   10s
Voice input                         [=====]
Camera frames                       . . . . . . . . . . . . . . .
ASR                                  [======]
Model                                       [===]
Response                                        [=======]
Speech report                                      [playing] .end
Navigation                                         [running] .done
Manipulation                                              .pick mode
Action                                                    [running]
                                                   | shared cursor

Selected evidence: source / direction / IDs / timing / outcome / limits
```

This is a wireframe, not a real trace or a claim that every lane is supported. M1 starts with the connection screen; each milestone adds its contracted portion of this design.

### Timeline behavior

- Time runs left to right on a shared labeled axis. Lanes identify resources or evidence categories; concurrent work overlaps correctly.
- Bars show measured intervals, markers show discrete events, and held-state bands show reports with freshness/gap semantics. A vertical event list is optional detail, not the main trace.
- Selecting a bar/marker opens readable evidence details. A keyboard-accessible cursor coordinates media playback and state-at-time inspection.
- Separate session-wide unassigned state from turn-associated evidence. Never fabricate model activity, execution completion or durations to fill the screen.
- Keep labels readable on smaller displays with stacked surrounding panels and a bounded timeline viewport/zoom if needed.

### Media behavior

- Use real captured images/clips or explicit missing/disabled/unsupported states. Fixture media is visibly labeled; no illustration counts as captured evidence.
- Provide image enlargement and timestamp selection, playable audio, and later video seek/play controls. Show source, recording time and synchronization uncertainty.
- Local playback only replays stored evidence. Outgoing synthesized speech is not a recording of sound emitted by the robot.
- Show corrupt, partial, missing, dropped or unsynchronized media without hiding the associated text/trace.

### Robot-state behavior

Show navigation, speech, action and manipulation where reported. Indicate latest timestamp, age, source and evidence association. Manipulation “enabled / pick mode” does not mean “arm moving” or “grasp succeeded.” Joint angles and geographic coordinates stay unavailable unless a verified source supplies them.

## Visible deliverable by release

| Release | Screen or added panel | Quick confidence check |
| --- | --- | --- |
| M1 | Connection + setup/verification | Watch genuine input freshness change after reconnect |
| M2 | Session browser + turn transcript/reply | Reopen saved turns after restart |
| M3 | Horizontal trace + inspector | Select overlapping spans and inspect their IDs |
| M4A | Audio players + waveform | Play input/output and seek along the trace |
| M4B | Thumbnail strip + full image | Select the correct captured scene and timestamp |
| M4C | Video player + synchronized cursor | Seek a saved clip to a known event |
| M5 | Provider spans + failure explanation | Identify a controlled delay/timeout visually |
| M6 | State summaries + outcome lanes | Distinguish reported completion from missing confirmation |

## Guided verification panel

Every milestone provides **Verify this milestone** with fixture and robot sections. Show prerequisites, numbered actions, expected UI changes, observed evidence, result and recovery guidance. Use Passed / Failed / Pending / Unsupported. The result derives from captured checks, not a user-selectable success badge.

Fixture buttons run repeatable scenarios through the actual application. Hardware steps guide the operator through a real interaction; starting a check does not silently move the robot. Save reports automatically and make them reopenable from the UI. Display failures to write reports/logs rather than claiming they were saved.

The [verification contract](VERIFICATION.md) defines evidence and release requirements.
