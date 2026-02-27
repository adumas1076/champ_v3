import { useState, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useRoomContext,
  DisconnectButton,
} from "@livekit/components-react";
import "@livekit/components-styles";

interface VoiceCallProps {
  brainUrl: string;
}

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || "";

function CallControls() {
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const [muted, setMuted] = useState(false);

  const toggleMute = useCallback(() => {
    const localParticipant = room.localParticipant;
    localParticipant.setMicrophoneEnabled(muted);
    setMuted(!muted);
  }, [room, muted]);

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="w-32 h-32 rounded-full bg-champ-accent/20 border-2 border-champ-accent flex items-center justify-center">
        <div
          className={`w-20 h-20 rounded-full ${
            connectionState === "connected"
              ? "bg-champ-green animate-pulse"
              : "bg-champ-accent"
          }`}
        />
      </div>

      <p className="text-lg font-medium">
        {connectionState === "connected"
          ? "Talking to Champ..."
          : connectionState === "connecting"
          ? "Connecting..."
          : "Disconnected"}
      </p>

      <div className="flex items-center gap-4">
        <button
          onClick={toggleMute}
          className={`px-6 py-3 rounded-lg font-medium transition-colors ${
            muted
              ? "bg-champ-yellow/20 text-champ-yellow border border-champ-yellow/30"
              : "bg-champ-card border border-champ-border text-white hover:bg-champ-border"
          }`}
        >
          {muted ? "Unmute" : "Mute"}
        </button>

        <DisconnectButton className="px-6 py-3 rounded-lg font-medium bg-champ-red/20 text-champ-red border border-champ-red/30 hover:bg-champ-red/30 transition-colors">
          End Call
        </DisconnectButton>
      </div>

      <RoomAudioRenderer />
    </div>
  );
}

export default function VoiceCall({ brainUrl }: VoiceCallProps) {
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");

  const startCall = useCallback(async () => {
    setConnecting(true);
    setError("");

    try {
      // Get token from Brain
      const tokenRes = await fetch(`${brainUrl}/v1/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-room" }),
      });

      if (!tokenRes.ok) {
        throw new Error(`Token request failed: ${tokenRes.status}`);
      }

      const tokenData = await tokenRes.json();

      // Dispatch agent to the room
      await fetch(`${brainUrl}/v1/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-room" }),
      });

      setToken(tokenData.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start call");
    } finally {
      setConnecting(false);
    }
  }, [brainUrl]);

  const handleDisconnect = useCallback(() => {
    setToken("");
  }, []);

  if (!LIVEKIT_URL) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-champ-red text-lg">
          VITE_LIVEKIT_URL not configured
        </p>
        <p className="text-champ-muted text-sm mt-2">
          Set it in your .env file or Vercel environment variables
        </p>
      </div>
    );
  }

  // Active call
  if (token) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <LiveKitRoom
          serverUrl={LIVEKIT_URL}
          token={token}
          connect={true}
          audio={true}
          video={false}
          onDisconnected={handleDisconnect}
        >
          <CallControls />
        </LiveKitRoom>
      </div>
    );
  }

  // Idle screen
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6">
      <div className="w-40 h-40 rounded-full bg-champ-card border-2 border-champ-border flex items-center justify-center">
        <svg
          className="w-16 h-16 text-champ-muted"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
          />
        </svg>
      </div>

      <div className="text-center">
        <h1 className="text-2xl font-bold mb-2">Talk to Champ</h1>
        <p className="text-champ-muted">
          Start a voice conversation with your AI assistant
        </p>
      </div>

      {error && (
        <div className="bg-champ-red/10 border border-champ-red/30 text-champ-red rounded-lg px-4 py-2 text-sm">
          {error}
        </div>
      )}

      <button
        onClick={startCall}
        disabled={connecting}
        className="px-8 py-4 rounded-xl text-lg font-semibold bg-champ-accent hover:bg-champ-accent/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {connecting ? "Connecting..." : "Start Call"}
      </button>
    </div>
  );
}
