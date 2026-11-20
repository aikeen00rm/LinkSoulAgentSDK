# SDK reference and compatibility checklist

## Baseline, not verification

The intended API family is Python LinkSoul AgentSDK v1.5.0 for one A3 Ultra. The official v150 documentation previously offered `linksoul_agentsdk-1.5.0a1` and described it as a snapshot/alpha. This fresh checkout has no installed SDK and no accepted hardware results. Recheck the official distribution, install/lock the selected package, compare its actual signatures and record firmware compatibility during implementation. Do not describe an alpha wheel as a verified stable 1.5.0 release.

## Official references

- [Overview, downloads and authentication](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en)
- [Passive callbacks and response flow](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/guide/passive_callbacks)
- [Callback API](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/api/passive_callbacks)
- [Architecture](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/guide/architecture)
- [Robot-state modules](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/guide/robot_states)
- [Active operations](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/guide/active_operations)
- [A3 Ultra interaction setup](https://open.agibot.com/docs/en/aimdk/a3-ultra/v3_3/dev_guide/08-interactive_guide)

Read only the relevant guide/API plus installed code for the integration being implemented. A guide's schema is not proof the selected firmware publishes that module.

## Integration constraints to verify

- v1.4+ documentation uses application ID/key/secret and HMAC signing. Select the correct regional gateway and keep credentials server-side. Verify TLS certificate/hostname checking and logging behavior in the selected package.
- One passive callback per SDK instance, registered before initialization. Callbacks participate in the custom-agent interaction pipeline; transparent observation of all built-in conversations is unproven.
- The multimodal class name is `AudioVideo2TtsCallback`. Earlier inspected signatures used `on_request(agent_id, event_id, flag, buf, param, response)` without `item_id`; verify this anew rather than copying another callback's signature.
- Audio input requires application ASR for a transcript; model and TTS providers are application dependencies. Returning response chunks is not an automatic inference service.
- Verify flag semantics per hook. Documentation distinguishes audio/video request flags (speech start/audio/end/H.264) from shared `on_video_frame` flags (H.264/image); they are not interchangeable.
- Shared hooks include robot online/offline, frames, state and histories where supported. Agent identity is a platform identity, not automatically a physical serial number.
- Valid response ordering includes interruption before new response/skill content in the documented flow. Preserve required behavior when instrumenting or changing callbacks.
- Chunks may share event IDs. History snapshots require deduplication. Inspect actual send/error/ack semantics before labeling an operation delivered.
- Task flows, extended skills and teleop have separate contracts; preview APIs need explicit support verification. These are not required for a basic recorder.

## State coverage to investigate in M6

| Module | Intended display | Limit |
| --- | --- | --- |
| `tts_status` | Playback lifecycle; event/item IDs where supplied | Robot-reported playback, not independent audio verification |
| `locomotion_status` | Navigation waiting/running/paused/completed/failed; task IDs | Requires publication and actual task correlation |
| `robot_pose` | Local position/orientation, optional velocity | Map/odometry frame; not assumed GPS |
| `current_location` | Semantic location and coordinate metadata | Retain source coordinate meaning |
| `planned_path` | Optional navigation path context | Not needed for initial state-lane acceptance |
| `manipulation` | `is_on` and optional pick/place/assist mode | Availability/mode, not arm joint angles or grasp success |
| `action_status` | Action/task progress, possibly multiple concurrent tasks | Task correlation required; array/object shapes may differ |

State values may be strings, numbers, objects or arrays. Parse according to module shape and retain original evidence. Missing fields remain unavailable. Joint telemetry needs a separate supported source; camera imagery must not be mislabeled measured robot pose.

## Compatibility record to fill

| Item | Verified value |
| --- | --- |
| Robot model | Owner reports A3 Ultra; physical association pending |
| Firmware / developer entitlement | Pending |
| Deployment host / image architecture | Pending |
| SDK distribution / exact version / hash | Pending |
| Python / locked dependencies | Pending |
| Region / gateway / authentication | Pending; credentials excluded |
| Agent template / callback configuration | Pending |
| Actual audio/image/video format and timing | Pending |
| Application inference providers | Pending |
| Published state modules / schemas | Pending |
| Built-in conversation observation | Unproven |

Append concise dated findings with sources, installed-package checks and actual hardware evidence. Keep documentation facts separate from observed behavior.

## Installed-package findings — M1, 2026-11-20

Installed official `linksoul_agentsdk-1.5.0a1-py3-none-any.whl` from the v1.5.0 documentation distribution; its download/hash and all dependencies are in `uv.lock`. Studio 0.1.0 uses Python 3.14.7, FastAPI 0.121.3, Uvicorn 0.38.0 and Jinja2 3.1.6. Host and tested container are arm64. Other architectures are unverified.

Rechecked the official [v1.5.0 guide](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en) and [passive callbacks](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/api/passive_callbacks), plus installed `agent_sdk.py`, `client/linksky_client.py` and passive ASR callback implementation. Registration precedes initialize; release removes the instance and stops owned resources. ASR request takes agent ID, event ID, text, param and response. Tests use actual SDK registration/release while replacing initialize to prevent network access.

The installed transport's default TLS options disable certificate verification. M1 overrides `_build_sslopt` to require certificates and hostname validation. `set_linksky_client_factory` and private `_on_close`/`_on_error` hooks provide the narrow pinned boundary. Auth code zero follows websocket open; display this as gateway transport connectivity, not proof of physical identity. The SDK can swallow send failures and logs payloads, so M1 suppresses formatted SDK logs and stores warning/error classifications only; `response.on_error` is labeled attempted, never delivered. Actual gateway authentication, TLS negotiation, reconnect behavior, firmware and hardware callbacks remain pending. Do not generalize the fixture/installed-package tests into robot evidence.

## M2 text/history boundary — 2026-11-20

Rechecked the official [passive guide](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/guide/passive_callbacks) and [callback API](https://open-eu.agibot.com/docs/linksoul/agentsdk_docs/python/v150/en/api/passive_callbacks), installed `passive/asr2_llm.py`, `passive/base.py`, `function_call.py` and `client/linksky_client.py` in 1.5.0a1. Asr2LlmResponse methods are `on_interrupt(event_id, "chat", None)`, `on_llm_item_delta(event_id,item_id,text)`, `on_llm_item_done(event_id,item_id)` and `on_llm_done(event_id)`. The guide requires interrupt first. M2 generates its outgoing item ID; it does not invent an inbound item ID. The installed transport returns None and can swallow send errors; Studio records attempted and call-returned evidence only. No acknowledgement or physical playback is established.

`on_histories(agent_id,event_id,histories)` supplies HistoryInfo objects with timestamp/query/answer/complete/event_id. The outer callback ID is not substituted for missing entry IDs. History text is retained as a bounded separate snapshot; it never overwrites locally captured outgoing chunks or advances send/acceptance state. Repeated identical snapshots with identity deduplicate, while snapshots without identity remain unassigned records. Installed-package callback tests include actual SDK registration and HistoryInfo objects, with network initialization disabled.

The minimal real provider follows the official [Ollama chat API](https://docs.ollama.com/api/chat): POST `/api/chat` with model/messages and `stream:false`; validate done/message.content. Its HTTP contract was tested against an isolated local server. A live Ollama model and A3 Ultra interaction were not available, so real model output, firmware behavior, agent configuration, history publication and playback remain pending. No provider package or robot capability was assumed from fixture success.
