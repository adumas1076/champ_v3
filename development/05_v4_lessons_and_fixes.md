# CHAMP V3/V4 — Lessons, Fixes, and Multimodality Reference

## Date: 2026-03-16

---

## Critical Fix: OpenAI Billing

**Symptom:** Champ connects to room, session starts, greeting generates — but NO audio plays.
**Root Cause:** OpenAI credit balance was -$0.53. The Realtime API silently rejects with `insufficient_quota`.
**Fix:** Add credits at https://platform.openai.com/settings/organization/billing
**Prevention:** Enable "Auto recharge" on the billing page.

### Debugging Workflow (use this order):
1. Check LiveKit Playground Events tab for `realtime_model_error`
2. If error says `insufficient_` → **billing issue, not code**
3. Check OpenAI, Anthropic, Google, Deepgram billing — whichever API is failing
4. Only debug code AFTER confirming all API keys have funds

---

## Friday Pattern (Proven Entrypoint Order)

**Source:** `reference/friday_jarvis-main/agent.py` + GUIDE.md Section 12

The working entrypoint order is:
```python
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            video_enabled=True,
        ),
    )

    await ctx.connect()  # AFTER session.start()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )
```

### Key Differences from Old V3 Pattern:
| Old V3 | Friday Pattern (Fixed) |
|--------|----------------------|
| `ctx.connect()` first | `session.start()` first |
| `RoomOptions(audio_input=True, ...)` | `RoomInputOptions(video_enabled=True)` |
| `AgentSession(video_sampler=...)` | `AgentSession()` — empty |
| `noise_cancellation` import | Removed (was blocking) |
| No `agent_name` in WorkerOptions | `agent_name="champ"` required for dispatch |

### Why `agent_name="champ"` Matters:
The Brain's `/v1/dispatch` sends `agent_name: "champ"`. LiveKit routes the job to a worker registered with that name. Without it, the dispatch never reaches the agent.

---

## LiveKit Multimodality Reference

### Vision (Camera + Screen Share)

**Simple (Realtime model — what we use):**
```python
room_input_options=RoomInputOptions(
    video_enabled=True,  # Auto-samples frames from camera/screen share
)
```
- Samples 1 frame/sec during user speech, 1 frame/3sec otherwise
- Resizes to 1024x1024 JPEG automatically
- Camera and screen share can't run simultaneously — screen share wins

**Advanced (Manual frame capture for non-realtime LLMs):**
```python
class Assistant(Agent):
    def __init__(self):
        self._latest_frame = None
        self._video_stream = None
        super().__init__(instructions="...")

    async def on_enter(self):
        room = get_job_context().room
        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_VIDEO:
                self._video_stream = rtc.VideoStream(track)
                asyncio.create_task(self._read_stream())

    async def on_user_turn_completed(self, turn_ctx, new_message):
        if self._latest_frame:
            new_message.content.append(ImageContent(image=self._latest_frame))
```

### Text Input/Output (Chat alongside Voice)

**Custom text handler:**
```python
def custom_text_input_handler(session, event):
    if event.text.startswith("/"):
        # Handle commands
        return
    session.interrupt()
    session.generate_reply(user_input=event.text)

await session.start(
    room_options=room_io.RoomOptions(
        text_input=room_io.TextInputOptions(
            text_input_cb=custom_text_input_handler
        )
    )
)
```

**Manual text reply:**
```python
session.generate_reply(user_input="Custom user message here")
```

**Toggle audio dynamically:**
```python
session.input.set_audio_enabled(False)   # stop listening
session.output.set_audio_enabled(False)  # stop speaking
# ... do non-verbal task ...
session.input.set_audio_enabled(True)    # resume
```

### Audio Features

**Say with no interruption:**
```python
await session.say("Important message", allow_interruptions=False)
```

**Background audio (ambient + thinking sounds):**
```python
from livekit.agents import BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip

background_audio = BackgroundAudioPlayer(
    ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=0.8),
    thinking_sound=[
        AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
    ],
)
await background_audio.start(room=ctx.room, agent_session=session)
```

**Cached TTS (preload common phrases):**
```python
HOLD_FRAMES = []
async def preload(tts):
    async for event in tts.synthesize("Let me check that for you."):
        HOLD_FRAMES.append(event.frame)

# Use in tool:
@function_tool()
async def my_tool(self, context: RunContext, query: str):
    context.session.say("Let me check...", audio=cached_audio(), add_to_chat_ctx=False)
    result = await do_work(query)
    return result
```

### Image Input (Upload/Byte Stream)

**Receive images from frontend:**
```python
async def on_enter(self):
    get_job_context().room.register_byte_stream_handler("images", self._on_image)

async def _on_image(self, reader, participant_identity):
    image_bytes = bytes()
    async for chunk in reader:
        image_bytes += chunk
    chat_ctx = self.chat_ctx.copy()
    chat_ctx.add_message(role="user", content=[
        ImageContent(image=f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}")
    ])
    await self.update_chat_ctx(chat_ctx)
```

---

## What We're Adding to CHAMP

| Feature | Status | What It Does |
|---------|--------|-------------|
| Vision (camera/screen) | Already working via `video_enabled=True` | Champ sees your screen/camera |
| Text chat + voice | Already working via V3 UI chat panel | Type while talking |
| Background thinking sounds | To add | Keyboard typing sound while Champ processes |
| Cached TTS for hold messages | To add | Instant "Let me check..." while tools run |
| Image upload via byte stream | To add | Drag images into chat for Champ to analyze |
| Dynamic audio toggle | To add | Mute/unmute Champ programmatically |

---

## V3 Terminal Startup (5 terminals)

```
Terminal 1 — LiteLLM (port 4001):
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
litellm --config litellm_config.yaml --port 4001

Terminal 2 — Brain (port 8100):
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python -m brain.main

Terminal 3 — Frontend (port 3000):
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3/frontend
npm run dev

Terminal 4 — Agent (LiveKit):
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python agent.py dev

Terminal 5 — Ears (port 8101):
cd c:/Users/libby/OneDrive/Desktop/tool_shed/CHAMP/champ_v3
venv/Scripts/activate
python -m ears
```
