# ============================================
# CHAMP V3 -- Ears Listener
# Brick 7: Always-on wake word detection
# Captures mic -> openWakeWord -> LiveKit room
#
# Run: python -m ears.listener
# ============================================
# "Built to build. Born to create."

import asyncio
import json as _json
import logging
import sys
import time

import keyboard
import numpy as np
import sounddevice as sd
from openwakeword.model import Model as OWWModel

from livekit import rtc
from livekit.api import AccessToken, VideoGrants

from ears.config import EarsSettings, load_ears_settings

logger = logging.getLogger(__name__)


# ---- State machine states ----
class ListenerState:
    LISTENING = "listening"
    ACTIVATING = "activating"
    CONVERSATION = "conversation"
    COOLDOWN = "cooldown"


class WakeWordDetector:
    """Thin wrapper around openWakeWord."""

    def __init__(self, settings: EarsSettings):
        self.settings = settings
        model_paths = None
        if settings.custom_model_path:
            model_paths = [settings.custom_model_path]

        self.model = OWWModel(
            wakeword_models=(
                model_paths if model_paths else [settings.wake_model]
            ),
            vad_threshold=settings.vad_threshold,
            inference_framework="onnx",
        )
        # Find the actual model key openWakeWord uses
        self.wake_model_key = settings.wake_model
        if self.model.models:
            self.wake_model_key = list(self.model.models.keys())[0]

        logger.info(
            f"Wake word detector ready: model={self.wake_model_key}, "
            f"threshold={settings.wake_threshold}, "
            f"vad_threshold={settings.vad_threshold}"
        )

    def detect(self, audio_frame: np.ndarray) -> float:
        """Feed an 80ms audio frame (1280 int16 samples @ 16kHz).
        Returns confidence score 0.0-1.0."""
        prediction = self.model.predict(audio_frame)
        score = prediction.get(self.wake_model_key, 0.0)
        return float(score)

    def reset(self):
        """Reset internal state after activation."""
        self.model.reset()


class LiveKitBridge:
    """Manages LiveKit room connection, mic publish, and speaker playback."""

    PLAYBACK_SAMPLE_RATE = 48000  # LiveKit default output rate

    def __init__(self, settings: EarsSettings):
        self.settings = settings
        self.room: rtc.Room | None = None
        self.audio_source: rtc.AudioSource | None = None
        self.track: rtc.LocalAudioTrack | None = None
        self._connected = False
        self._playback_stream: sd.OutputStream | None = None
        self._playback_task: asyncio.Task | None = None

    def _generate_token(self) -> str:
        """Generate a LiveKit access token for the ears participant."""
        token = AccessToken(
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret,
        )
        token.with_identity(self.settings.participant_identity)
        token.with_name("Champ Ears")
        token.with_grants(VideoGrants(
            room_join=True,
            room=self.settings.room_name,
            can_publish=True,
            can_subscribe=True,
        ))
        return token.to_jwt()

    def _start_speaker(self) -> None:
        """Open speaker output stream for playback."""
        self._playback_stream = sd.OutputStream(
            samplerate=self.PLAYBACK_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        self._playback_stream.start()
        logger.info("Speaker output stream opened")

    def _stop_speaker(self) -> None:
        """Close speaker output stream."""
        if self._playback_stream:
            self._playback_stream.stop()
            self._playback_stream.close()
            self._playback_stream = None
            logger.info("Speaker output stream closed")

    async def _play_audio_track(self, track: rtc.RemoteAudioTrack) -> None:
        """Subscribe to a remote audio track and play through speakers."""
        logger.info(f"Playing audio from track: {track.sid}")
        audio_stream = rtc.AudioStream(
            track,
            sample_rate=self.PLAYBACK_SAMPLE_RATE,
            num_channels=1,
        )
        async for event in audio_stream:
            if not self._connected or not self._playback_stream:
                break
            frame_data = np.frombuffer(event.frame.data, dtype=np.int16)
            try:
                self._playback_stream.write(frame_data)
            except Exception as e:
                logger.warning(f"Playback write error: {e}")
                break

    def _on_track_subscribed(
        self, track: rtc.Track, publication, participant
    ) -> None:
        """Called when a remote track is subscribed."""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(
                f"Subscribed to audio track from {participant.identity}"
            )
            self._playback_task = asyncio.create_task(
                self._play_audio_track(track)  # type: ignore
            )

    async def connect(self) -> None:
        """Join LiveKit room, publish mic, and listen for agent audio."""
        self.room = rtc.Room()
        jwt_token = self._generate_token()

        # Listen for incoming audio tracks (agent responses)
        self.room.on("track_subscribed", self._on_track_subscribed)

        logger.info(
            f"Connecting to LiveKit room '{self.settings.room_name}'..."
        )
        await self.room.connect(self.settings.livekit_url, jwt_token)
        logger.info(f"Connected to room: {self.room.name}")

        # Open speaker for playback
        self._start_speaker()

        # Create audio source at 16kHz mono
        self.audio_source = rtc.AudioSource(
            sample_rate=self.settings.sample_rate,
            num_channels=self.settings.channels,
        )

        # Create and publish track
        self.track = rtc.LocalAudioTrack.create_audio_track(
            "ears-microphone",
            self.audio_source,
        )

        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await self.room.local_participant.publish_track(
            self.track, options
        )
        self._connected = True
        logger.info("Mic audio track published to LiveKit")

    async def send_audio(
        self, audio_data: bytes, samples_per_channel: int
    ) -> None:
        """Push an audio frame to the LiveKit room."""
        if not self._connected or not self.audio_source:
            return
        frame = rtc.AudioFrame(
            data=audio_data,
            sample_rate=self.settings.sample_rate,
            num_channels=self.settings.channels,
            samples_per_channel=samples_per_channel,
        )
        await self.audio_source.capture_frame(frame)

    async def disconnect(self) -> None:
        """Leave the LiveKit room and stop playback."""
        self._connected = False
        if self._playback_task:
            self._playback_task.cancel()
            self._playback_task = None
        self._stop_speaker()
        if self.room:
            logger.info("Disconnecting from LiveKit room...")
            await self.room.disconnect()
            self.room = None
            self.audio_source = None
            self.track = None
            logger.info("Disconnected from LiveKit")

    @property
    def is_connected(self) -> bool:
        return self._connected


class EarsListener:
    """
    Main orchestrator. State machine:
      LISTENING -> ACTIVATING -> CONVERSATION -> COOLDOWN -> LISTENING
    """

    def __init__(self, settings: EarsSettings | None = None):
        self.settings = settings or load_ears_settings()
        self.detector = WakeWordDetector(self.settings)
        self.bridge = LiveKitBridge(self.settings)
        self.state = ListenerState.LISTENING
        self._running = False
        self._audio_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._last_speech_time: float = 0.0

        # 1280 samples for 80ms @ 16kHz
        self.frame_samples = int(
            self.settings.sample_rate * self.settings.frame_ms / 1000
        )

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback -- runs in audio thread."""
        if status:
            logger.warning(f"Audio status: {status}")
        mono = indata[:, 0].copy()
        try:
            self._audio_queue.put_nowait(mono)
        except asyncio.QueueFull:
            pass  # Drop frame if processing can't keep up

    async def _process_listening(self, frame: np.ndarray) -> None:
        """LISTENING state: run wake word detection."""
        score = self.detector.detect(frame)
        if score >= self.settings.wake_threshold:
            logger.info(
                f"WAKE WORD DETECTED! score={score:.3f} "
                f"(threshold={self.settings.wake_threshold})"
            )
            self.state = ListenerState.ACTIVATING
            await self._activate()

    async def _activate(self) -> None:
        """ACTIVATING: connect to LiveKit room."""
        try:
            await self.bridge.connect()
            self.state = ListenerState.CONVERSATION
            self._last_speech_time = time.monotonic()
            self.detector.reset()
            logger.info("Entered CONVERSATION state")
        except Exception as e:
            logger.error(f"Failed to connect to LiveKit: {e}")
            self.state = ListenerState.LISTENING

    async def _process_conversation(self, frame: np.ndarray) -> None:
        """CONVERSATION state: forward mic audio to LiveKit."""
        audio_bytes = frame.astype(np.int16).tobytes()
        await self.bridge.send_audio(audio_bytes, len(frame))

        # Simple energy check for speech presence
        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
        if rms > 200:  # Speech threshold (int16 range)
            self._last_speech_time = time.monotonic()

        # Agent is talking = conversation is active
        if self.bridge._playback_task and not self.bridge._playback_task.done():
            self._last_speech_time = time.monotonic()

        # Check silence timeout
        elapsed = time.monotonic() - self._last_speech_time
        if elapsed > self.settings.silence_timeout_s:
            logger.info(
                f"Silence timeout ({self.settings.silence_timeout_s}s). "
                "Ending conversation."
            )
            await self._deactivate()

    async def _deactivate(self) -> None:
        """Disconnect from LiveKit and enter cooldown."""
        await self.bridge.disconnect()
        self.state = ListenerState.COOLDOWN
        logger.info(f"Cooldown for {self.settings.cooldown_s}s...")
        await asyncio.sleep(self.settings.cooldown_s)
        self.state = ListenerState.LISTENING
        logger.info("Back to LISTENING state")

    async def _keyboard_trigger(self) -> None:
        """Watch for NumLock key press as manual wake trigger."""
        logger.info("Keyboard trigger active: press NumLock to wake Champ")
        loop = asyncio.get_event_loop()
        trigger_event = asyncio.Event()

        def on_numlock(_):
            loop.call_soon_threadsafe(trigger_event.set)

        keyboard.on_press_key("num lock", on_numlock)

        try:
            while self._running:
                trigger_event.clear()
                try:
                    await asyncio.wait_for(trigger_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if self.state == ListenerState.LISTENING:
                    logger.info("MANUAL TRIGGER (NumLock) -- activating!")
                    self.state = ListenerState.ACTIVATING
                    await self._activate()
        finally:
            keyboard.unhook_all()

    async def _start_health_server(self, port: int = 8101) -> None:
        """Start a lightweight TCP health check server (no extra deps)."""
        async def handle_client(reader, writer):
            try:
                await reader.read(4096)  # Consume HTTP request
                body = _json.dumps({
                    "status": "ok",
                    "service": "champ-v3-ears",
                    "state": self.state,
                    "room": self.settings.room_name,
                    "connected": self.bridge.is_connected,
                })
                response = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"\r\n{body}"
                )
                writer.write(response.encode())
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()

        try:
            server = await asyncio.start_server(
                handle_client, "127.0.0.1", port
            )
            logger.info(
                f"Ears health server on http://127.0.0.1:{port}/health"
            )
            self._health_server = server
        except Exception as e:
            logger.warning(f"Failed to start health server: {e}")

    async def run(self) -> None:
        """Main loop. Opens mic stream, processes frames by state."""
        self._running = True

        # Start health check endpoint
        await self._start_health_server()

        logger.info(
            f"Ears listener starting | device={self.settings.audio_device} | "
            f"model={self.settings.wake_model} | "
            f"room={self.settings.room_name}"
        )

        stream = sd.InputStream(
            samplerate=self.settings.sample_rate,
            channels=self.settings.channels,
            dtype="int16",
            blocksize=self.frame_samples,
            device=self.settings.audio_device,
            callback=self._audio_callback,
        )

        with stream:
            logger.info("Mic stream open. Listening for wake word...")

            # Run keyboard trigger alongside audio processing
            kb_task = asyncio.create_task(self._keyboard_trigger())

            try:
                while self._running:
                    try:
                        frame = await asyncio.wait_for(
                            self._audio_queue.get(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

                    if self.state == ListenerState.LISTENING:
                        await self._process_listening(frame)
                    elif self.state == ListenerState.CONVERSATION:
                        await self._process_conversation(frame)
            finally:
                kb_task.cancel()

        logger.info("Ears listener stopped")

    def stop(self):
        """Signal the listener to stop."""
        self._running = False


# ---- Entry point ----
async def main():
    settings = load_ears_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("=" * 60)
    print("CHAMP V3 -- EARS LISTENER")
    print(f"Wake word: {settings.wake_model}")
    print(f"Threshold: {settings.wake_threshold}")
    print(f"Room: {settings.room_name}")
    print("Say the wake word or press NumLock to activate Champ!")
    print("=" * 60)

    listener = EarsListener(settings)

    try:
        await listener.run()
    except KeyboardInterrupt:
        listener.stop()
    finally:
        if listener.bridge.is_connected:
            await listener.bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
