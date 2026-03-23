/**
 * CHAMP Avatar Lab — Standalone test page for avatar rendering.
 *
 * This is a SEPARATE page from VoiceCall.tsx.
 * Tests the avatar video track without touching the main call UI.
 *
 * Route: /avatar-lab
 * Agent: avatar/agent_avatar.py (separate from main agent.py)
 */

import { useState, useCallback, useEffect, useRef } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useRoomContext,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { RoomEvent, Track } from "livekit-client";

// ─── Config ──────────────────────────────────────────────────────────────────

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || "";
const BRAIN_URL = import.meta.env.VITE_BRAIN_URL || "http://127.0.0.1:8100";

// ─── Avatar Video Overlay ────────────────────────────────────────────────────

function AvatarVideoOverlay() {
  const room = useRoomContext();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasAvatar, setHasAvatar] = useState(false);
  const [avatarInfo, setAvatarInfo] = useState("");

  useEffect(() => {
    if (!room) return;

    const checkForAvatar = () => {
      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (
            pub.source === Track.Source.Camera &&
            pub.track &&
            !pub.isMuted
          ) {
            if (videoRef.current) {
              pub.track.attach(videoRef.current);
            }
            setHasAvatar(true);
            setAvatarInfo(
              `${p.identity} | ${pub.track.mediaStreamTrack?.getSettings()?.width || "?"}x${pub.track.mediaStreamTrack?.getSettings()?.height || "?"}`
            );
            return;
          }
        }
      }
      setHasAvatar(false);
      setAvatarInfo("");
    };

    checkForAvatar();
    room.on(RoomEvent.TrackSubscribed, checkForAvatar);
    room.on(RoomEvent.TrackUnsubscribed, checkForAvatar);
    room.on(RoomEvent.TrackMuted, checkForAvatar);
    room.on(RoomEvent.TrackUnmuted, checkForAvatar);

    return () => {
      room.off(RoomEvent.TrackSubscribed, checkForAvatar);
      room.off(RoomEvent.TrackUnsubscribed, checkForAvatar);
      room.off(RoomEvent.TrackMuted, checkForAvatar);
      room.off(RoomEvent.TrackUnmuted, checkForAvatar);
      if (videoRef.current) {
        const el = videoRef.current;
        for (const p of room.remoteParticipants.values()) {
          for (const pub of p.trackPublications.values()) {
            pub.track?.detach(el);
          }
        }
      }
    };
  }, [room]);

  return (
    <>
      {/* Avatar video — renders on top of static image when available */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`absolute inset-0 w-full h-full object-cover z-[1] transition-opacity duration-500 ${
          hasAvatar ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Avatar status badge */}
      <div className="absolute top-4 right-4 z-10">
        <div
          className={`px-3 py-1.5 rounded-full text-xs font-mono backdrop-blur-sm ${
            hasAvatar
              ? "bg-green-500/20 text-green-400 border border-green-500/30"
              : "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
          }`}
        >
          {hasAvatar ? `AVATAR LIVE — ${avatarInfo}` : "AVATAR: waiting for video track..."}
        </div>
      </div>
    </>
  );
}

// ─── Debug Panel ─────────────────────────────────────────────────────────────

function DebugPanel() {
  const room = useRoomContext();
  const [stats, setStats] = useState({
    participants: 0,
    videoTracks: 0,
    audioTracks: 0,
  });

  useEffect(() => {
    if (!room) return;

    const update = () => {
      let videoTracks = 0;
      let audioTracks = 0;
      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (pub.kind === "video") videoTracks++;
          if (pub.kind === "audio") audioTracks++;
        }
      }
      setStats({
        participants: room.remoteParticipants.size + 1,
        videoTracks,
        audioTracks,
      });
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [room]);

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-black/60 backdrop-blur-sm rounded-lg p-3 text-xs font-mono text-white/70 space-y-1">
      <div>Participants: {stats.participants}</div>
      <div>Video tracks: {stats.videoTracks}</div>
      <div>Audio tracks: {stats.audioTracks}</div>
    </div>
  );
}

// ─── Active Session (inside LiveKitRoom) ─────────────────────────────────────

function ActiveSession({ onDisconnect }: { onDisconnect: () => void }) {
  const room = useRoomContext();

  const handleEnd = useCallback(() => {
    room.disconnect();
    onDisconnect();
  }, [room, onDisconnect]);

  return (
    <div className="fixed inset-0 bg-black">
      {/* Background — Champ's face (static image, replaced by video when avatar is live) */}
      <div className="absolute inset-0">
        <img
          src="/operators/champ/champ_bio_01.png"
          alt="Champ"
          className="w-full h-full object-cover"
        />
      </div>

      {/* Avatar video overlay */}
      <AvatarVideoOverlay />

      {/* Debug panel */}
      <DebugPanel />

      {/* Top bar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
        <div className="flex items-center gap-2 bg-black/40 backdrop-blur-sm rounded-full px-4 py-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-white text-sm font-medium">Avatar Lab</span>
        </div>
      </div>

      {/* Bottom controls */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex items-center gap-4">
        <button
          onClick={handleEnd}
          className="px-6 py-3 rounded-full bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
        >
          End Session
        </button>
      </div>

      <RoomAudioRenderer />
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function AvatarLab() {
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");

  const startSession = useCallback(async () => {
    setConnecting(true);
    setError("");

    try {
      // Get token from Brain
      const tokenRes = await fetch(`${BRAIN_URL}/v1/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-avatar-lab" }),
      });

      if (!tokenRes.ok) throw new Error(`Token: ${tokenRes.status}`);
      const tokenData = await tokenRes.json();

      // Dispatch avatar agent
      await fetch(`${BRAIN_URL}/v1/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-avatar-lab" }),
      });

      setToken(tokenData.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    } finally {
      setConnecting(false);
    }
  }, []);

  const handleDisconnect = useCallback(() => {
    setToken("");
  }, []);

  // ── Lobby (no connection yet) ──

  if (!token) {
    return (
      <div className="fixed inset-0 bg-black">
        {/* Background */}
        <div className="absolute inset-0">
          <img
            src="/operators/champ/champ_bio_01.png"
            alt="Champ"
            className="w-full h-full object-cover brightness-50 blur-sm"
          />
        </div>

        {/* Center content */}
        <div className="relative z-10 flex flex-col items-center justify-center h-full gap-6">
          <h1 className="text-4xl font-bold text-white">Avatar Lab</h1>
          <p className="text-white/60 text-lg max-w-md text-center">
            Test the CHAMP avatar renderer. Starts a voice session with
            animated video — Champ's face moves, blinks, and lip-syncs in real time.
          </p>

          {error && (
            <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg text-sm">
              {error}
            </div>
          )}

          <button
            onClick={startSession}
            disabled={connecting}
            className="px-8 py-4 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium text-lg transition-colors"
          >
            {connecting ? "Connecting..." : "Start Avatar Session"}
          </button>

          {!LIVEKIT_URL && (
            <p className="text-red-400 text-sm">
              VITE_LIVEKIT_URL not set — check .env
            </p>
          )}
        </div>
      </div>
    );
  }

  // ── Connected ──

  return (
    <LiveKitRoom
      serverUrl={LIVEKIT_URL}
      token={token}
      connect={true}
      onDisconnected={handleDisconnect}
      audio={true}
      video={false}
    >
      <ActiveSession onDisconnect={handleDisconnect} />
    </LiveKitRoom>
  );
}
