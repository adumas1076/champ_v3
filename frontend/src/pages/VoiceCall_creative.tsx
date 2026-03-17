import { useState, useCallback, useEffect, useRef } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useRoomContext,
} from "@livekit/components-react";
import "@livekit/components-styles";
import {
  MoreHorizontal,
  Mic,
  MicOff,
  PhoneOff,
  Volume2,
  VolumeX,
  Settings,
  MessageSquareWarning,
  MessageCircle,
  Users,
  UserPlus,
  Send,
  Video,
  VideoOff,
  X,
  ScreenShare,
  ScreenShareOff,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { RoomEvent } from "livekit-client";

// ─── Types ───────────────────────────────────────────────────────────────────

interface VoiceCallProps {
  brainUrl: string;
}

interface Participant {
  id: string;
  name: string;
  avatar?: string;
  isMuted: boolean;
  isActive: boolean;
}

interface ChatMessage {
  id: string;
  sender: string;
  text: string;
  timestamp: Date;
  isAgent: boolean;
}

type ConnectionPhase = "idle" | "connecting" | "connected" | "ended" | "error";
type PanelTab = "participants" | "chat";

// ─── Operator Config ─────────────────────────────────────────────────────────

const OPERATOR_IMAGE = "/operators/champ/champ_bio_01.png";
const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || "";

// ─── LiveBadge (from Skipper + connection states) ────────────────────────────

function LiveBadge({ phase }: { phase: ConnectionPhase }) {
  const config: Record<ConnectionPhase, { color: string; label: string; pulse: boolean }> = {
    idle: { color: "bg-champ-muted", label: "Offline", pulse: false },
    connecting: { color: "bg-champ-yellow", label: "Connecting...", pulse: true },
    connected: { color: "bg-[#00c950]", label: "Live", pulse: true },
    ended: { color: "bg-champ-red", label: "Ended", pulse: false },
    error: { color: "bg-champ-red", label: "Error", pulse: true },
  };

  const { color, label, pulse } = config[phase];

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-black/40 border border-white/10 rounded-full backdrop-blur-md">
      <div
        className={`w-2 h-2 rounded-full ${color} ${pulse ? "animate-pulse" : ""}`}
        style={pulse && phase === "connected" ? { boxShadow: "0 0 8px rgba(0,201,80,0.5)" } : {}}
      />
      <span className="text-white text-sm font-normal leading-none tracking-wide">
        {label}
      </span>
    </div>
  );
}

// ─── TimerBadge (from Skipper) ───────────────────────────────────────────────

function TimerBadge({ isRunning }: { isRunning: boolean }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!isRunning) return;
    setSeconds(0);
    const interval = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const m = Math.floor(seconds / 60);
  const s = seconds % 60;

  return (
    <div className="inline-flex items-center justify-center px-3 py-1.5 bg-black/40 border border-white/10 rounded-full backdrop-blur-md min-w-[60px]">
      <span className="text-white text-sm font-normal leading-none tracking-wide tabular-nums">
        {m}:{s.toString().padStart(2, "0")}
      </span>
    </div>
  );
}

// ─── PIP Thumbnail (tap-to-swap — from Skipper DraggablePip pattern) ────────

// ─── Draggable PIP (from Skipper DraggablePip — drag + tap-to-swap) ─────────

function PipThumbnail({
  participant,
  isSwapped,
  onSwap,
}: {
  participant: Participant;
  isSwapped: boolean;
  onSwap: () => void;
}) {
  const showingOperator = isSwapped;
  const label = showingOperator ? "Champ" : participant.name;
  const initial = label.charAt(0).toUpperCase();
  const dragRef = useRef({ startX: 0, startY: 0, didDrag: false });

  const handlePointerDown = (e: React.PointerEvent) => {
    dragRef.current.startX = e.clientX;
    dragRef.current.startY = e.clientY;
    dragRef.current.didDrag = false;
  };

  const handlePointerUp = () => {
    // Only swap if user didn't drag more than 10px
    if (!dragRef.current.didDrag) {
      onSwap();
    }
  };

  return (
    <motion.div
      drag
      dragMomentum={false}
      dragElastic={0.1}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onDrag={(_e, info) => {
        const dx = Math.abs(info.offset.x);
        const dy = Math.abs(info.offset.y);
        if (dx > 10 || dy > 10) {
          dragRef.current.didDrag = true;
        }
      }}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className="relative h-[148px] w-[200px] rounded-2xl overflow-hidden border-2 border-champ-accent/40 shrink-0 cursor-grab active:cursor-grabbing shadow-xl group z-50"
      style={{ touchAction: "none" }}
      title="Drag to move · Tap to swap"
    >
      {showingOperator ? (
        <img
          src={OPERATOR_IMAGE}
          alt="Champ"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          style={{ objectPosition: "center 20%" }}
        />
      ) : participant.avatar ? (
        <img
          src={participant.avatar}
          alt={participant.name}
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
        />
      ) : (
        <div className="absolute inset-0 bg-champ-card flex items-center justify-center pointer-events-none">
          <span className="text-4xl font-bold text-white/30">{initial}</span>
        </div>
      )}

      {/* Swap hint overlay on hover */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center pointer-events-none">
        <span className="text-white text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          Tap to swap
        </span>
      </div>

      {/* Name badge */}
      <div className="absolute bottom-2 left-2 px-2.5 py-1 bg-black/40 rounded-full backdrop-blur-sm pointer-events-none">
        <span className="text-white text-xs font-semibold">{label}</span>
      </div>

      {/* Mic status icon */}
      <div
        className={`absolute bottom-2 right-2 p-1.5 rounded-lg pointer-events-none ${
          participant.isMuted ? "bg-champ-red/80" : "bg-champ-accent"
        }`}
      >
        {participant.isMuted ? (
          <MicOff size={12} className="text-white" />
        ) : (
          <Mic size={12} className="text-white" />
        )}
      </div>
    </motion.div>
  );
}

// ─── ParticipantStrip ────────────────────────────────────────────────────────

function ParticipantStrip({
  participants,
  isSwapped,
  onSwap,
}: {
  participants: Participant[];
  isSwapped: boolean;
  onSwap: () => void;
}) {
  if (participants.length === 0) return null;

  return (
    <div className="flex gap-3 items-end">
      {participants.map((p) => (
        <PipThumbnail
          key={p.id}
          participant={p}
          isSwapped={isSwapped}
          onSwap={onSwap}
        />
      ))}
    </div>
  );
}

// ─── ParticipantListItem (right panel — from Figma participant list) ─────────

function ParticipantListItem({ participant }: { participant: Participant }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors group">
      {/* Avatar */}
      <div className="relative shrink-0">
        {participant.avatar ? (
          <img
            src={participant.avatar}
            alt={participant.name}
            className="w-9 h-9 rounded-full object-cover"
          />
        ) : (
          <div className="w-9 h-9 rounded-full bg-champ-accent/30 flex items-center justify-center">
            <span className="text-sm font-semibold text-champ-accent">
              {participant.name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        {participant.isActive && (
          <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-[#00c950] rounded-full border-2 border-[#111]" />
        )}
      </div>

      {/* Name */}
      <span className="text-white/90 text-sm font-medium flex-1 truncate">
        {participant.name}
      </span>

      {/* Mic status */}
      <div className={`p-1 rounded-md ${participant.isMuted ? "text-champ-red" : "text-white/40"}`}>
        {participant.isMuted ? <MicOff size={14} /> : <Mic size={14} />}
      </div>
    </div>
  );
}

// ─── ChatBubble ─────────────────────────────────────────────────────────────

function ChatBubble({ message }: { message: ChatMessage }) {
  const timeStr = message.timestamp.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  return (
    <div className={`flex gap-2.5 ${message.isAgent ? "" : "flex-row-reverse"}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
          message.isAgent ? "bg-champ-accent/30 text-champ-accent" : "bg-white/10 text-white/60"
        }`}
      >
        {message.sender.charAt(0).toUpperCase()}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${message.isAgent ? "" : "text-right"}`}>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-white/60 text-xs font-medium">{message.sender}</span>
          <span className="text-white/30 text-[10px]">{timeStr}</span>
        </div>
        <div
          className={`px-3 py-2 rounded-2xl text-sm leading-relaxed ${
            message.isAgent
              ? "bg-white/10 text-white/90 rounded-tl-md"
              : "bg-champ-accent text-white rounded-tr-md"
          }`}
        >
          {message.text}
        </div>
      </div>
    </div>
  );
}

// ─── SidePanel (Participants + Chat — from Figma right panel) ────────────────

function SidePanel({
  isOpen,
  onClose,
  participants,
  messages,
  onSendMessage,
  isLive,
}: {
  isOpen: boolean;
  onClose: () => void;
  participants: Participant[];
  messages: ChatMessage[];
  onSendMessage: (text: string) => void;
  isLive: boolean;
}) {
  const [activeTab, setActiveTab] = useState<PanelTab>("chat");
  const [draft, setDraft] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !isLive) return;
    onSendMessage(text);
    setDraft("");
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%", opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={{ type: "spring", damping: 28, stiffness: 300 }}
          className="absolute top-0 right-0 bottom-0 w-[360px] z-40 flex flex-col bg-[#111]/90 backdrop-blur-xl border-l border-white/10"
        >
          {/* Panel Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <div className="flex items-center gap-2">
              {activeTab === "participants" ? (
                <Users size={16} className="text-white/60" />
              ) : (
                <MessageCircle size={16} className="text-white/60" />
              )}
              <span className="text-white font-semibold text-sm">
                {activeTab === "participants" ? "Participants" : "Chats"}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {activeTab === "participants" && (
                <button
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-champ-accent rounded-full text-white text-xs font-medium hover:bg-champ-accent/80 transition-colors"
                  title="Add Participant"
                >
                  <UserPlus size={12} />
                  Add Participant
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/10">
            <button
              onClick={() => setActiveTab("participants")}
              className={`flex-1 py-2.5 text-xs font-semibold transition-colors ${
                activeTab === "participants"
                  ? "text-white border-b-2 border-champ-accent"
                  : "text-white/40 hover:text-white/60"
              }`}
            >
              Participants ({participants.length})
            </button>
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex-1 py-2.5 text-xs font-semibold transition-colors ${
                activeTab === "chat"
                  ? "text-white border-b-2 border-champ-accent"
                  : "text-white/40 hover:text-white/60"
              }`}
            >
              Chat
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {activeTab === "participants" ? (
              <div className="p-2">
                {participants.map((p) => (
                  <ParticipantListItem key={p.id} participant={p} />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-3 p-4">
                {messages.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center py-12">
                    <p className="text-white/30 text-sm">No messages yet</p>
                  </div>
                ) : (
                  messages.map((msg) => <ChatBubble key={msg.id} message={msg} />)
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Chat Input — only show on chat tab */}
          {activeTab === "chat" && (
            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-2">
                <Mic size={16} className="text-white/30 shrink-0 cursor-pointer hover:text-white/60" />
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Type Something..."
                  disabled={!isLive}
                  className="flex-1 bg-transparent text-white text-sm placeholder-white/30 outline-none disabled:opacity-40"
                />
                <button
                  onClick={handleSend}
                  disabled={!draft.trim() || !isLive}
                  className="p-1.5 rounded-full bg-champ-accent text-white disabled:opacity-30 hover:bg-champ-accent/80 transition-colors shrink-0"
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── CallControls (Skipper UI + CHAMP LiveKit wiring) ────────────────────────

function CreativeOperatorControls({
  phase,
  onEndCall,
  onTogglePanel,
  isPanelOpen,
}: {
  phase: ConnectionPhase;
  onEndCall: () => void;
  onTogglePanel: () => void;
  isPanelOpen: boolean;
}) {
  const room = useRoomContext();
  const [isMicOn, setIsMicOn] = useState(true);
  const [isSpeakerOn, setIsSpeakerOn] = useState(true);
  const [isCameraOn, setIsCameraOn] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isLive = phase === "connected";
  const buttonBase =
    "w-12 h-12 rounded-full backdrop-blur-xl flex items-center justify-center transition-all border";

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleMic = useCallback(() => {
    if (!isLive) return;
    const next = !isMicOn;
    room.localParticipant.setMicrophoneEnabled(next);
    setIsMicOn(next);
  }, [room, isMicOn, isLive]);

  const toggleSpeaker = useCallback(() => {
    setIsSpeakerOn((prev) => !prev);
    const audioElements = document.querySelectorAll("audio");
    audioElements.forEach((el) => {
      (el as HTMLAudioElement).muted = isSpeakerOn;
    });
    setShowMenu(false);
  }, [isSpeakerOn]);

  const toggleCamera = useCallback(() => {
    if (!isLive) return;
    const next = !isCameraOn;
    room.localParticipant.setCameraEnabled(next);
    setIsCameraOn(next);
  }, [room, isCameraOn, isLive]);

  const toggleScreenShare = useCallback(async () => {
    if (!isLive) return;
    const next = !isScreenSharing;
    try {
      await room.localParticipant.setScreenShareEnabled(next);
      setIsScreenSharing(next);
    } catch {
      // User cancelled screen share picker
    }
    setShowMenu(false);
  }, [room, isScreenSharing, isLive]);

  return (
    <div
      className={`flex flex-col gap-4 items-center transition-opacity duration-300 ${
        phase === "ended" ? "opacity-0 pointer-events-none" : "opacity-100"
      }`}
    >
      {/* More menu */}
      <div className="relative" ref={menuRef}>
        <AnimatePresence>
          {showMenu && (
            <motion.div
              initial={{ opacity: 0, x: -10, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: -10, scale: 0.95 }}
              className="absolute left-full ml-3 bottom-0 w-48 bg-[#111] border border-white/10 rounded-xl shadow-2xl overflow-hidden backdrop-blur-xl z-50"
            >
              <div className="p-1">
                <button
                  onClick={toggleSpeaker}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors text-sm"
                >
                  {isSpeakerOn ? <Volume2 size={16} /> : <VolumeX size={16} className="text-red-400" />}
                  {isSpeakerOn ? "Mute Speaker" : "Unmute Speaker"}
                </button>
                <div className="h-px bg-white/5 my-0.5" />
                <button
                  onClick={toggleScreenShare}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors text-sm"
                >
                  {isScreenSharing ? (
                    <ScreenShareOff size={16} className="text-red-400" />
                  ) : (
                    <ScreenShare size={16} />
                  )}
                  {isScreenSharing ? "Stop Sharing" : "Share Screen"}
                </button>
                <div className="h-px bg-white/5 my-0.5" />
                <button
                  onClick={() => setShowMenu(false)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors text-sm"
                >
                  <Settings size={16} />
                  Audio Settings
                </button>
                <button
                  onClick={() => setShowMenu(false)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors text-sm"
                >
                  <MessageSquareWarning size={16} />
                  Report Issue
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          onClick={() => setShowMenu(!showMenu)}
          disabled={!isLive}
          className={`${buttonBase} ${
            showMenu
              ? "bg-white/20 text-white border-white/30"
              : "bg-white/10 text-white hover:bg-white/20 border-white/10 hover:border-white/30"
          } ${!isLive ? "opacity-40 cursor-not-allowed" : "hover:scale-105"}`}
          title="More Options"
        >
          <MoreHorizontal size={20} />
        </button>
      </div>

      {/* Camera toggle */}
      <button
        onClick={toggleCamera}
        disabled={!isLive}
        className={`${buttonBase} ${
          isCameraOn
            ? "bg-white/10 text-white hover:bg-white/20 border-white/10 hover:border-white/30"
            : "bg-white/10 text-white/60 hover:bg-white/20 border-white/10 hover:border-white/30"
        } ${!isLive ? "opacity-40 cursor-not-allowed" : "hover:scale-105"}`}
        title={isCameraOn ? "Turn Off Camera" : "Turn On Camera"}
      >
        {isCameraOn ? <Video size={20} /> : <VideoOff size={20} />}
      </button>

      {/* Speaker toggle */}
      <button
        onClick={toggleSpeaker}
        disabled={!isLive}
        className={`${buttonBase} ${
          isSpeakerOn
            ? "bg-white/10 text-white hover:bg-white/20 border-white/10 hover:border-white/30"
            : "bg-red-500/20 text-red-400 border-red-500/50 hover:bg-red-500/30"
        } ${!isLive ? "opacity-40 cursor-not-allowed" : "hover:scale-105"}`}
        title={isSpeakerOn ? "Mute Speaker" : "Unmute Speaker"}
      >
        {isSpeakerOn ? <Volume2 size={20} /> : <VolumeX size={20} />}
      </button>

      {/* Mic toggle */}
      <button
        onClick={toggleMic}
        disabled={!isLive}
        className={`${buttonBase} ${
          isMicOn
            ? "bg-white/10 text-white hover:bg-white/20 border-white/10 hover:border-white/30"
            : "bg-red-500/20 text-red-400 border-red-500/50 hover:bg-red-500/30"
        } ${!isLive ? "opacity-40 cursor-not-allowed" : "hover:scale-105"}`}
        title={isMicOn ? "Mute Mic" : "Unmute Mic"}
      >
        {isMicOn ? <Mic size={20} /> : <MicOff size={20} />}
      </button>

      {/* Panel toggle (chat/participants) */}
      <button
        onClick={onTogglePanel}
        className={`${buttonBase} ${
          isPanelOpen
            ? "bg-champ-accent/30 text-champ-accent border-champ-accent/50"
            : "bg-white/10 text-white hover:bg-white/20 border-white/10 hover:border-white/30"
        } ${!isLive ? "opacity-40 cursor-not-allowed" : "hover:scale-105"}`}
        disabled={!isLive}
        title="Chat & Participants"
      >
        <MessageCircle size={20} />
      </button>

      {/* End call */}
      <button
        onClick={onEndCall}
        disabled={!isLive}
        className={`${buttonBase} border-0 ${
          isLive
            ? "bg-champ-red text-white hover:scale-110 shadow-[0_4px_20px_rgba(239,68,68,0.4)]"
            : "bg-champ-red/30 text-white/40 cursor-not-allowed"
        }`}
        title="End Session"
      >
        <PhoneOff size={20} />
      </button>

    </div>
  );
}

// ─── Inner Session (mounted inside LiveKitRoom) ──────────────────────────────

function ActiveSession({
  onEndCall,
  participants,
  messages,
  onAddMessage,
  isPanelOpen,
  onTogglePanel,
  isSwapped,
  onSwap,
}: {
  onEndCall: () => void;
  participants: Participant[];
  messages: ChatMessage[];
  onAddMessage: (msg: ChatMessage) => void;
  isPanelOpen: boolean;
  onTogglePanel: () => void;
  isSwapped: boolean;
  onSwap: () => void;
}) {
  const connectionState = useConnectionState();
  const room = useRoomContext();

  const phase: ConnectionPhase =
    connectionState === "connected"
      ? "connected"
      : connectionState === "connecting"
      ? "connecting"
      : "ended";

  // ── Listen for agent responses (text streams + data packets) ──
  const handlersRegistered = useRef(false);

  useEffect(() => {
    if (!room || handlersRegistered.current) return;
    handlersRegistered.current = true;

    // Method 1: Text stream API (lk.chat)
    try {
      room.registerTextStreamHandler("lk.chat", async (reader, participantInfo) => {
        const text = await reader.readAll();
        if (!text.trim()) return;
        onAddMessage({
          id: `msg-agent-${Date.now()}-${Math.random()}`,
          sender: participantInfo?.identity || "Champ",
          text,
          timestamp: new Date(),
          isAgent: true,
        });
      });
    } catch {
      // Already registered
    }

    // Method 2: Text stream API (lk.transcription)
    try {
      room.registerTextStreamHandler("lk.transcription", async (reader, participantInfo) => {
        if (reader.info?.attributes?.["lk.transcription_final"] !== "true") return;
        const text = await reader.readAll();
        if (!text.trim()) return;
        // Skip user speech transcriptions (have track ID)
        if (reader.info?.attributes?.["lk.transcribed_track_id"]) return;
        onAddMessage({
          id: `msg-transcript-${Date.now()}-${Math.random()}`,
          sender: participantInfo?.identity || "Champ",
          text,
          timestamp: new Date(),
          isAgent: true,
        });
      });
    } catch {
      // Already registered
    }

    // Method 3: Data channel fallback (older agents send transcriptions this way)
    const handleData = (payload: Uint8Array, _participant: unknown) => {
      try {
        const decoded = new TextDecoder().decode(payload);
        const data = JSON.parse(decoded);
        // Handle transcription segments from agent
        if (data.type === "transcription" && data.segments) {
          for (const seg of data.segments) {
            if (seg.final && seg.text?.trim()) {
              onAddMessage({
                id: `msg-data-${seg.id || Date.now()}-${Math.random()}`,
                sender: "Champ",
                text: seg.text,
                timestamp: new Date(),
                isAgent: true,
              });
            }
          }
        }
      } catch {
        // Not JSON — ignore
      }
    };
    room.on(RoomEvent.DataReceived, handleData);

    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room, onAddMessage]);

  // ── Send text message via LiveKit ──
  const sendMessage = useCallback(async (text: string) => {
    onAddMessage({
      id: `msg-${Date.now()}`,
      sender: "You",
      text,
      timestamp: new Date(),
      isAgent: false,
    });

    try {
      await room.localParticipant.sendText(text, { topic: "lk.chat" });
    } catch (err) {
      console.error("Failed to send text:", err);
    }
  }, [room, onAddMessage]);

  return (
    <OperatorLayout
      phase={phase}
      onConnect={undefined}
      participants={participants}
      messages={messages}
      onSendMessage={sendMessage}
      isPanelOpen={isPanelOpen}
      onTogglePanel={onTogglePanel}
      isSwapped={isSwapped}
      onSwap={onSwap}
    >
      <CreativeOperatorControls
        phase={phase}
        onEndCall={onEndCall}
        onTogglePanel={onTogglePanel}
        isPanelOpen={isPanelOpen}
      />
      <RoomAudioRenderer />
    </OperatorLayout>
  );
}

// ─── Operator Layout (shared across all states) ──────────────────────────────

function OperatorLayout({
  phase,
  onConnect,
  participants,
  messages = [],
  onSendMessage,
  isPanelOpen = false,
  onTogglePanel,
  isSwapped = false,
  onSwap,
  error,
  children,
}: {
  phase: ConnectionPhase;
  onConnect?: () => void;
  participants: Participant[];
  messages?: ChatMessage[];
  onSendMessage?: (text: string) => void;
  isPanelOpen?: boolean;
  onTogglePanel?: () => void;
  isSwapped?: boolean;
  onSwap?: () => void;
  error?: string;
  children?: React.ReactNode;
}) {
  const isLive = phase === "connected";
  const showLobby = phase === "idle" || phase === "connecting" || phase === "error";

  // Background blur/brightness per state (from Skipper IdleScreen pattern)
  const bgClass = isLive
    ? "brightness-100 scale-100 blur-0"
    : phase === "ended"
    ? "brightness-50 scale-100 blur-sm"
    : "brightness-75 scale-110 blur-[6px]";

  return (
    <div className="fixed inset-0 bg-black overflow-hidden">
      {/* Background — Operator or User (swappable) */}
      <div className="absolute inset-0 overflow-hidden">
        {isSwapped ? (
          <div className="absolute inset-0 bg-champ-card flex items-center justify-center">
            <span className="text-8xl font-bold text-white/10">You</span>
          </div>
        ) : (
          <img
            src={OPERATOR_IMAGE}
            alt="CHAMP Operator"
            className={`absolute inset-0 w-full h-full object-cover transition-all duration-700 ${bgClass}`}
            style={{ objectPosition: "center 20%" }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        )}
        {/* Gradient overlay — heavier on lobby, lighter when live */}
        <div
          className={`absolute inset-0 pointer-events-none transition-opacity duration-700 ${
            isLive
              ? "bg-gradient-to-t from-black/60 via-transparent to-black/20"
              : "bg-gradient-to-b from-black/50 via-black/40 to-black/70"
          }`}
        />
      </div>

      {/* ─── LOBBY STATE (idle / connecting / error) ─── */}
      <AnimatePresence>
        {showLobby && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.4 } }}
            className="absolute inset-0 z-30 flex flex-col items-center justify-center"
          >
            {/* Centered branding + start button */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1, duration: 0.5 }}
              className="flex flex-col items-center text-center"
            >
              <p className="text-white/50 text-sm tracking-widest uppercase mb-3">
                {phase === "connecting" ? "Connecting..." : "Tap to start your session"}
              </p>
              <h1 className="text-white text-5xl font-bold tracking-tight mb-1 drop-shadow-2xl">
                Champ
              </h1>
              <p className="text-white/60 text-lg mb-10">Creative Operator</p>

              {/* Start button or spinner */}
              {phase === "idle" && onConnect && (
                <motion.button
                  onClick={onConnect}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="w-20 h-20 rounded-full bg-champ-accent flex items-center justify-center shadow-[0_0_40px_rgba(59,130,246,0.4)] hover:shadow-[0_0_60px_rgba(59,130,246,0.6)] transition-shadow"
                >
                  <PhoneOff size={28} className="text-white rotate-[135deg]" />
                </motion.button>
              )}

              {phase === "connecting" && (
                <div className="w-20 h-20 rounded-full border-4 border-white/10 border-t-champ-accent animate-spin" />
              )}

              {phase === "error" && (
                <div className="flex flex-col items-center gap-4">
                  <div className="px-5 py-2.5 bg-champ-red/20 border border-champ-red/30 rounded-xl text-champ-red text-sm">
                    {error || "Connection failed"}
                  </div>
                  {onConnect && (
                    <button
                      onClick={onConnect}
                      className="px-8 py-3 rounded-xl text-base font-semibold bg-champ-accent hover:bg-champ-accent/80 text-white transition-colors"
                    >
                      Try Again
                    </button>
                  )}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── ENDED STATE ─── */}
      <AnimatePresence>
        {phase === "ended" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center z-30 bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="text-center"
            >
              <h3 className="text-white text-3xl font-bold mb-2">Session Ended</h3>
              <p className="text-white/50 mb-8">Ready to reconnect?</p>
              {onConnect && (
                <motion.button
                  onClick={onConnect}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-8 py-3 rounded-xl text-lg font-semibold bg-champ-accent hover:bg-champ-accent/80 text-white transition-colors"
                >
                  New Session
                </motion.button>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── ACTIVE STATE (connected) ─── */}
      {/* Side Panel (Participants + Chat) */}
      {onSendMessage && onTogglePanel && (
        <SidePanel
          isOpen={isPanelOpen}
          onClose={onTogglePanel}
          participants={participants}
          messages={messages}
          onSendMessage={onSendMessage}
          isLive={isLive}
        />
      )}

      {/* Content Layer — only visible when connected */}
      <div
        className={`absolute inset-0 z-20 flex flex-col justify-between pointer-events-none transition-opacity duration-500 ${
          isLive ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      >
        {/* Top Bar */}
        <div className="flex justify-between items-start p-6 pointer-events-auto">
          <div className="flex items-center gap-3">
            <LiveBadge phase={phase} />
            <div className="ml-2">
              <h1 className="text-white text-xl font-bold tracking-tight leading-none drop-shadow-lg">
                Champ
              </h1>
              <p className="text-white/60 text-xs mt-0.5 tracking-wide">Creative Operator</p>
            </div>
          </div>
          <TimerBadge isRunning={isLive} />
        </div>

        {/* Middle — left sidebar controls */}
        <div className="flex items-center px-6 pointer-events-auto">
          {children}
        </div>

        {/* Bottom Bar */}
        <div className="flex items-end justify-between p-6 pointer-events-auto">
          <ParticipantStrip participants={participants} isSwapped={isSwapped} onSwap={onSwap || (() => {})} />
        </div>
      </div>
    </div>
  );
}

// ─── Main VoiceCall Component ────────────────────────────────────────────────

export default function VoiceCall({ brainUrl }: VoiceCallProps) {
  const [token, setToken] = useState("");
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [error, setError] = useState("");
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [isSwapped, setIsSwapped] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  // V1: single user participant — data model supports array for future multi-participant
  const [participants] = useState<Participant[]>([
    {
      id: "user-1",
      name: "You",
      isMuted: false,
      isActive: true,
    },
  ]);

  const togglePanel = useCallback(() => {
    setIsPanelOpen((prev) => !prev);
  }, []);

  const toggleSwap = useCallback(() => {
    setIsSwapped((prev) => !prev);
  }, []);

  const startCall = useCallback(async () => {
    setPhase("connecting");
    setError("");

    try {
      const tokenRes = await fetch(`${brainUrl}/v1/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-room" }),
      });

      if (!tokenRes.ok) {
        throw new Error(`Token request failed: ${tokenRes.status}`);
      }

      const tokenData = await tokenRes.json();

      await fetch(`${brainUrl}/v1/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: "champ-room" }),
      });

      setToken(tokenData.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to connect");
      setPhase("error");
    }
  }, [brainUrl]);

  const endCall = useCallback(() => {
    setToken("");
    setPhase("ended");
    setIsPanelOpen(false);
  }, []);

  const handleNewSession = useCallback(() => {
    setToken("");
    setPhase("idle");
    setError("");
  }, []);

  if (!LIVEKIT_URL) {
    return (
      <OperatorLayout phase="error" participants={[]} error="VITE_LIVEKIT_URL not configured">
        <div />
      </OperatorLayout>
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
        onDisconnected={endCall}
      >
        <ActiveSession
          onEndCall={endCall}
          participants={participants}
          messages={messages}
          onAddMessage={addMessage}
          isPanelOpen={isPanelOpen}
          onTogglePanel={togglePanel}
          isSwapped={isSwapped}
          onSwap={toggleSwap}
        />
      </LiveKitRoom>
    );
  }

  return (
    <OperatorLayout
      phase={phase}
      onConnect={phase === "ended" ? handleNewSession : phase === "connecting" ? undefined : startCall}
      participants={phase === "idle" ? [] : participants}
      error={error}
    >
      <div />
    </OperatorLayout>
  );
}