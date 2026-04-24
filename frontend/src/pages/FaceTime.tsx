import { useState, useCallback, useEffect, useRef } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useRoomContext,
  useChat,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { ConnectionState, RoomEvent, Track, RemoteParticipant } from "livekit-client";
import { AnimatePresence, motion } from "motion/react";
import { Mic, MicOff, PhoneOff, MessageSquare, X, Send } from "lucide-react";

interface FaceTimeProps {
  brainUrl: string;
}

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || "";

// ─── Genesis Avatar Video ─────────────────────────────────────────────────

function AvatarVideo() {
  const room = useRoomContext();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasVideo, setHasVideo] = useState(false);
  const [agentName, setAgentName] = useState("Genesis");

  useEffect(() => {
    if (!room) return;

    const attachAvatar = () => {
      for (const p of room.remoteParticipants.values()) {
        // Pick up the agent's name
        if (p.name) setAgentName(p.name);

        for (const pub of p.trackPublications.values()) {
          if (
            pub.source === Track.Source.Camera &&
            pub.track &&
            !pub.isMuted
          ) {
            if (videoRef.current) {
              pub.track.attach(videoRef.current);
            }
            setHasVideo(true);
            return;
          }
        }
      }
      setHasVideo(false);
    };

    attachAvatar();
    room.on(RoomEvent.TrackSubscribed, attachAvatar);
    room.on(RoomEvent.TrackUnsubscribed, attachAvatar);
    room.on(RoomEvent.TrackMuted, attachAvatar);
    room.on(RoomEvent.TrackUnmuted, attachAvatar);

    return () => {
      room.off(RoomEvent.TrackSubscribed, attachAvatar);
      room.off(RoomEvent.TrackUnsubscribed, attachAvatar);
      room.off(RoomEvent.TrackMuted, attachAvatar);
      room.off(RoomEvent.TrackUnmuted, attachAvatar);
      if (videoRef.current) {
        for (const p of room.remoteParticipants.values()) {
          for (const pub of p.trackPublications.values()) {
            pub.track?.detach(videoRef.current!);
          }
        }
      }
    };
  }, [room]);

  return (
    <div className="relative w-full h-full bg-black">
      {/* Video fill */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-cover transition-opacity duration-500 ${
          hasVideo ? "opacity-100" : "opacity-0"
        }`}
      />

      {/* Fallback: Genesis photo when no video stream yet */}
      {!hasVideo && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative">
            <img
              src="/images/genesis-avatar.png"
              alt="Genesis"
              className="w-80 h-80 object-cover rounded-2xl opacity-60"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full border-4 border-white/30 border-t-white animate-spin" />
            </div>
          </div>
        </div>
      )}

      {/* Agent name label */}
      <div className="absolute top-6 left-6 z-10">
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-black/50 px-4 py-2 backdrop-blur-md">
          <div className={`w-2 h-2 rounded-full ${hasVideo ? "bg-green-400 animate-pulse" : "bg-yellow-400"}`} />
          <span className="text-white font-medium text-sm">{agentName}</span>
          {hasVideo && (
            <span className="text-white/50 text-xs">Live</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Chat Panel ────────────────────────────────────────────────────────────

function ChatPanel({ onClose }: { onClose: () => void }) {
  const { chatMessages, send } = useChat();
  const [message, setMessage] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleSend = () => {
    if (message.trim()) {
      send(message.trim());
      setMessage("");
    }
  };

  return (
    <motion.div
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="absolute top-0 right-0 w-96 h-full bg-black/80 backdrop-blur-xl border-l border-white/10 flex flex-col z-20"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <span className="text-white font-medium">Chat</span>
        <button onClick={onClose} className="text-white/50 hover:text-white transition-colors">
          <X size={20} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {chatMessages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.from?.identity === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                msg.from?.identity === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-white/10 text-white"
              }`}
            >
              {msg.message}
            </div>
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-white/10">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1 bg-white/10 rounded-full px-4 py-2 text-sm text-white placeholder-white/30 outline-none focus:ring-2 focus:ring-white/20"
          />
          <button
            onClick={handleSend}
            className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors"
          >
            <Send size={16} className="text-white" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ─── FaceTime Controls ──────────────────────────────────────────────────────

function FaceTimeSession() {
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const [muted, setMuted] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const toggleMute = useCallback(() => {
    room.localParticipant.setMicrophoneEnabled(muted);
    setMuted(!muted);
  }, [room, muted]);

  return (
    <div className="fixed inset-0 bg-black">
      {/* Full-screen avatar video */}
      <AvatarVideo />

      {/* Chat panel overlay */}
      <AnimatePresence>
        {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
      </AnimatePresence>

      {/* Bottom controls */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="absolute bottom-0 left-0 right-0 z-30"
      >
        <div className="flex items-center justify-center gap-4 pb-10 pt-20 bg-gradient-to-t from-black/80 to-transparent">
          {/* Mute */}
          <button
            onClick={toggleMute}
            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
              muted
                ? "bg-white text-black"
                : "bg-white/15 text-white backdrop-blur-md hover:bg-white/25"
            }`}
          >
            {muted ? <MicOff size={22} /> : <Mic size={22} />}
          </button>

          {/* End call */}
          <button
            onClick={() => room.disconnect()}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors"
          >
            <PhoneOff size={24} />
          </button>

          {/* Chat toggle */}
          <button
            onClick={() => setChatOpen(!chatOpen)}
            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
              chatOpen
                ? "bg-white text-black"
                : "bg-white/15 text-white backdrop-blur-md hover:bg-white/25"
            }`}
          >
            <MessageSquare size={22} />
          </button>
        </div>
      </motion.div>

      {/* Connection status */}
      {connectionState !== "connected" && (
        <div className="absolute inset-0 flex items-center justify-center z-40 bg-black/60">
          <div className="text-center">
            <div className="w-12 h-12 rounded-full border-4 border-white/20 border-t-white animate-spin mx-auto mb-4" />
            <p className="text-white/60 text-sm">
              {connectionState === "connecting" ? "Connecting to Genesis..." : "Reconnecting..."}
            </p>
          </div>
        </div>
      )}

      <RoomAudioRenderer />
    </div>
  );
}

// ─── Welcome Screen ──────────────────────────────────────────────────────────

function WelcomeScreen({ onStart, connecting }: { onStart: () => void; connecting: boolean }) {
  return (
    <div className="fixed inset-0 bg-black flex flex-col items-center justify-center">
      {/* Genesis preview */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <img
          src="/images/genesis-avatar.png"
          alt="Genesis"
          className="w-48 h-48 object-cover rounded-3xl shadow-2xl shadow-white/5"
        />
      </motion.div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-center mb-8"
      >
        <h1 className="text-3xl font-bold text-white mb-2">Genesis</h1>
        <p className="text-white/50 text-sm max-w-md">
          Live Creatiq Operator — your AI operator with real-time emotions,
          powered by Ditto and LiveKit.
        </p>
      </motion.div>

      <motion.button
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
        onClick={onStart}
        disabled={connecting}
        className="px-10 py-4 rounded-full bg-white text-black font-semibold text-sm uppercase tracking-wider hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {connecting ? "Connecting..." : "Start Call"}
      </motion.button>

      <p className="absolute bottom-6 text-white/20 text-xs">
        Powered by Cocreatiq OS
      </p>
    </div>
  );
}

// ─── Main FaceTime Page ─────────────────────────────────────────────────────

export default function FaceTime({ brainUrl }: FaceTimeProps) {
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);

  const startCall = useCallback(async () => {
    setConnecting(true);
    try {
      const tokenRes = await fetch(`${brainUrl}/v1/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "genesis-room" }),
      });
      if (!tokenRes.ok) throw new Error(`Token: ${tokenRes.status}`);
      const tokenData = await tokenRes.json();

      await fetch(`${brainUrl}/v1/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "genesis-room" }),
      });

      setToken(tokenData.token);
    } catch (e) {
      console.error("Failed to start call:", e);
    } finally {
      setConnecting(false);
    }
  }, [brainUrl]);

  if (!LIVEKIT_URL) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <p className="text-red-400">VITE_LIVEKIT_URL not configured</p>
      </div>
    );
  }

  if (token) {
    return (
      <LiveKitRoom
        serverUrl={LIVEKIT_URL}
        token={token}
        connect={true}
        audio={true}
        video={false}
        onDisconnected={() => setToken("")}
      >
        <FaceTimeSession />
      </LiveKitRoom>
    );
  }

  return <WelcomeScreen onStart={startCall} connecting={connecting} />;
}
