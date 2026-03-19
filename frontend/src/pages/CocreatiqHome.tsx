import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  Brain,
  Mic,
  Phone,
  Settings,
  Activity,
  Database,
  Globe,
  Terminal,
  Search,
  ChevronUp,
  Cpu,
  Zap,
  User,
  Layers,
  Wifi,
  BatteryFull,
  Signal,
  X,
} from "lucide-react";

// ─── Mock Data ──────────────────────────────────────────────────────────────

const MOCK = {
  brain: "Online" as const,
  phase: "Inference",
  tasks: 3,
  totalTasks: 5,
  memory: 67,
  uptime: "4h 23m",
};

const APPS = [
  { name: "Voice Call", icon: Phone, route: "/call", color: "#3b82f6" },
  { name: "Dashboard", icon: Activity, route: "/", color: "#22c55e" },
  { name: "Avatar Lab", icon: User, route: "/avatar-lab", color: "#a855f7" },
  { name: "Self Mode", icon: Cpu, route: null, color: "#f59e0b" },
  { name: "Browser", icon: Globe, route: null, color: "#06b6d4" },
  { name: "Settings", icon: Settings, route: null, color: "#6b7280" },
  { name: "Memory", icon: Database, route: null, color: "#ec4899" },
  { name: "Logs", icon: Terminal, route: null, color: "#10b981" },
];

const DOCK_APPS = [
  { name: "Call", icon: Phone, route: "/call", color: "#3b82f6" },
  { name: "Dashboard", icon: Activity, route: "/", color: "#22c55e" },
  { name: "Settings", icon: Settings, route: null, color: "#6b7280" },
  { name: "Memory", icon: Database, route: null, color: "#ec4899" },
];

// ─── Clock Hook ─────────────────────────────────────────────────────────────

function useClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

// ─── Status Bar ─────────────────────────────────────────────────────────────

function StatusBar({ time }: { time: Date }) {
  const formatted = time.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex items-center justify-between px-6 py-2 text-xs text-white/70">
      <div className="flex items-center gap-1.5 font-semibold text-white/90 tracking-wide">
        <Zap size={12} className="text-champ-accent" />
        <span>Cocreatiq</span>
      </div>
      <span className="font-medium tabular-nums">{formatted}</span>
      <div className="flex items-center gap-1.5">
        <Signal size={12} />
        <Wifi size={12} />
        <BatteryFull size={12} />
      </div>
    </div>
  );
}

// ─── Circular Gauge ─────────────────────────────────────────────────────────

function CircularGauge({
  value,
  size = 64,
  strokeWidth = 5,
  color = "#3b82f6",
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="rgba(255,255,255,0.08)"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
    </svg>
  );
}

// ─── Progress Ring (small) ──────────────────────────────────────────────────

function ProgressBar({
  value,
  max,
  color = "#3b82f6",
}: {
  value: number;
  max: number;
  color?: string;
}) {
  const pct = (value / max) * 100;
  return (
    <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden">
      <motion.div
        className="h-full rounded-full"
        style={{ backgroundColor: color }}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 1, ease: "easeOut" }}
      />
    </div>
  );
}

// ─── Widget Card ────────────────────────────────────────────────────────────

function WidgetCard({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`
        rounded-2xl p-5
        bg-white/[0.04] border border-white/[0.08]
        backdrop-blur-xl
        shadow-[0_8px_32px_rgba(0,0,0,0.4)]
        ${className}
      `}
    >
      {children}
    </motion.div>
  );
}

// ─── Brain Status Widget ────────────────────────────────────────────────────

function BrainStatusWidget() {
  return (
    <WidgetCard>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-champ-accent/15 flex items-center justify-center">
            <Brain size={18} className="text-champ-accent" />
          </div>
          <div>
            <p className="text-[11px] text-white/40 uppercase tracking-wider font-medium">
              Brain Status
            </p>
            <p className="text-sm font-semibold text-white mt-0.5">
              {MOCK.brain}
            </p>
          </div>
        </div>
        <motion.div
          className="w-2.5 h-2.5 rounded-full bg-champ-green mt-1"
          animate={{
            boxShadow: [
              "0 0 0px rgba(34,197,94,0.4)",
              "0 0 12px rgba(34,197,94,0.8)",
              "0 0 0px rgba(34,197,94,0.4)",
            ],
          }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
      <div className="flex items-center gap-2 text-xs text-white/40">
        <Cpu size={12} />
        <span>Phase: {MOCK.phase}</span>
        <span className="text-white/20">|</span>
        <span>Uptime: {MOCK.uptime}</span>
      </div>
    </WidgetCard>
  );
}

// ─── Active Tasks Widget ────────────────────────────────────────────────────

function ActiveTasksWidget() {
  return (
    <WidgetCard>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-champ-green/15 flex items-center justify-center">
            <Activity size={18} className="text-champ-green" />
          </div>
          <div>
            <p className="text-[11px] text-white/40 uppercase tracking-wider font-medium">
              Active Tasks
            </p>
            <p className="text-sm font-semibold text-white mt-0.5">
              {MOCK.tasks} of {MOCK.totalTasks} running
            </p>
          </div>
        </div>
      </div>
      <ProgressBar value={MOCK.tasks} max={MOCK.totalTasks} color="#22c55e" />
    </WidgetCard>
  );
}

// ─── Memory Widget ──────────────────────────────────────────────────────────

function MemoryWidget() {
  return (
    <WidgetCard>
      <div className="flex items-center gap-4">
        <div className="relative flex-shrink-0">
          <CircularGauge value={MOCK.memory} size={64} color="#a855f7" />
          <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white rotate-0">
            {MOCK.memory}%
          </span>
        </div>
        <div>
          <p className="text-[11px] text-white/40 uppercase tracking-wider font-medium">
            Memory
          </p>
          <p className="text-sm font-semibold text-white mt-0.5">
            Context Usage
          </p>
          <p className="text-xs text-white/30 mt-1">67k / 100k tokens</p>
        </div>
      </div>
    </WidgetCard>
  );
}

// ─── Quick Actions Widget ───────────────────────────────────────────────────

function QuickActionsWidget() {
  const navigate = useNavigate();

  const actions = [
    {
      label: "Voice Call",
      icon: Phone,
      color: "#3b82f6",
      bg: "bg-blue-500/15",
      route: "/call",
    },
    {
      label: "Self Mode",
      icon: Cpu,
      color: "#f59e0b",
      bg: "bg-amber-500/15",
      route: null,
    },
    {
      label: "Avatar Lab",
      icon: User,
      color: "#a855f7",
      bg: "bg-purple-500/15",
      route: "/avatar-lab",
    },
    {
      label: "Settings",
      icon: Settings,
      color: "#6b7280",
      bg: "bg-gray-500/15",
      route: null,
    },
  ];

  return (
    <WidgetCard>
      <p className="text-[11px] text-white/40 uppercase tracking-wider font-medium mb-3">
        Quick Actions
      </p>
      <div className="grid grid-cols-2 gap-2.5">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={() => a.route && navigate(a.route)}
            className="flex items-center gap-2.5 rounded-xl p-3 bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.08] transition-colors active:scale-95"
          >
            <div
              className={`w-8 h-8 rounded-lg ${a.bg} flex items-center justify-center flex-shrink-0`}
            >
              <a.icon size={15} style={{ color: a.color }} />
            </div>
            <span className="text-xs font-medium text-white/80">
              {a.label}
            </span>
          </button>
        ))}
      </div>
    </WidgetCard>
  );
}

// ─── Voice Orb ──────────────────────────────────────────────────────────────

function VoiceOrb() {
  const navigate = useNavigate();

  return (
    <motion.button
      onClick={() => navigate("/call")}
      className="relative w-16 h-16 rounded-full flex items-center justify-center z-20"
      whileTap={{ scale: 0.9 }}
    >
      {/* Outer pulse ring */}
      <motion.div
        className="absolute inset-0 rounded-full bg-champ-accent/30"
        animate={{
          scale: [1, 1.35, 1],
          opacity: [0.4, 0, 0.4],
        }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
      />
      {/* Secondary ring */}
      <motion.div
        className="absolute inset-0 rounded-full bg-champ-accent/20"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.1, 0.3],
        }}
        transition={{
          duration: 2.5,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 0.3,
        }}
      />
      {/* Core */}
      <div className="w-full h-full rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-[0_0_30px_rgba(59,130,246,0.5)]">
        <Mic size={22} className="text-white" />
      </div>
    </motion.button>
  );
}

// ─── Dock ───────────────────────────────────────────────────────────────────

function Dock() {
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-center gap-6">
      {DOCK_APPS.map((app) => (
        <button
          key={app.name}
          onClick={() => app.route && navigate(app.route)}
          className="flex flex-col items-center gap-1 active:scale-90 transition-transform"
        >
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center"
            style={{ backgroundColor: `${app.color}20` }}
          >
            <app.icon size={20} style={{ color: app.color }} />
          </div>
          <span className="text-[10px] text-white/40">{app.name}</span>
        </button>
      ))}
    </div>
  );
}

// ─── App Drawer ─────────────────────────────────────────────────────────────

function AppDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const filtered = APPS.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-hidden rounded-t-3xl"
          >
            <div className="bg-white/[0.06] backdrop-blur-2xl border-t border-white/[0.1] h-full flex flex-col">
              {/* Handle + close */}
              <div className="flex items-center justify-center pt-3 pb-1">
                <div className="w-10 h-1 rounded-full bg-white/20" />
              </div>
              <div className="flex items-center justify-between px-6 pb-2">
                <h2 className="text-lg font-semibold text-white">Apps</h2>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors"
                >
                  <X size={16} className="text-white/60" />
                </button>
              </div>

              {/* Search */}
              <div className="px-6 pb-4">
                <div className="flex items-center gap-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] px-3.5 py-2.5">
                  <Search size={16} className="text-white/30 flex-shrink-0" />
                  <input
                    type="text"
                    placeholder="Search apps..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-transparent text-sm text-white placeholder-white/30 outline-none w-full"
                  />
                </div>
              </div>

              {/* Grid */}
              <div className="px-6 pb-10 overflow-y-auto">
                <div className="grid grid-cols-4 gap-5">
                  {filtered.map((app) => (
                    <motion.button
                      key={app.name}
                      whileTap={{ scale: 0.9 }}
                      onClick={() => {
                        if (app.route) {
                          navigate(app.route);
                          onClose();
                        }
                      }}
                      className="flex flex-col items-center gap-2"
                    >
                      <div
                        className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg"
                        style={{
                          background: `linear-gradient(135deg, ${app.color}30, ${app.color}15)`,
                          border: `1px solid ${app.color}25`,
                        }}
                      >
                        <app.icon size={24} style={{ color: app.color }} />
                      </div>
                      <span className="text-[11px] text-white/50 font-medium truncate w-full text-center">
                        {app.name}
                      </span>
                    </motion.button>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function CocreatiqHome() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const time = useClock();

  return (
    <div
      className="fixed inset-0 flex flex-col overflow-hidden select-none"
      style={{
        background:
          "radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.08) 0%, #0a0a0a 60%)",
        fontFamily:
          "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* Subtle grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.015] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Status Bar */}
      <StatusBar time={time} />

      {/* Date & Greeting */}
      <div className="px-6 pt-2 pb-4">
        <p className="text-white/30 text-xs font-medium">
          {time.toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </p>
        <h1 className="text-2xl font-bold text-white mt-0.5 tracking-tight">
          Good{" "}
          {time.getHours() < 12
            ? "Morning"
            : time.getHours() < 18
              ? "Afternoon"
              : "Evening"}
        </h1>
      </div>

      {/* Scrollable Widgets Area */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-3 relative z-10 scrollbar-hide">
        {/* Two-column grid on wider screens */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <BrainStatusWidget />
          <ActiveTasksWidget />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <MemoryWidget />
          <QuickActionsWidget />
        </div>

        {/* Spacer for bottom area */}
        <div className="h-36" />
      </div>

      {/* Bottom Area — Dock + Voice Orb + Drawer Toggle */}
      <div className="absolute bottom-0 inset-x-0 z-20">
        {/* Gradient fade */}
        <div className="h-20 bg-gradient-to-t from-[#0a0a0a] to-transparent pointer-events-none" />

        <div className="bg-[#0a0a0a] pb-4 pt-1 space-y-4">
          {/* Dock */}
          <Dock />

          {/* Voice Orb + Drawer Toggle */}
          <div className="flex items-center justify-center gap-6">
            {/* Swipe-up / drawer toggle */}
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex flex-col items-center gap-0.5"
            >
              <motion.div
                animate={{ y: [0, -3, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <ChevronUp size={18} className="text-white/25" />
              </motion.div>
              <span className="text-[10px] text-white/25">Apps</span>
            </button>

            {/* Voice Orb */}
            <VoiceOrb />

            {/* Layers icon for balance */}
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex flex-col items-center gap-1"
            >
              <Layers size={18} className="text-white/25" />
              <span className="text-[10px] text-white/25">Drawer</span>
            </button>
          </div>
        </div>
      </div>

      {/* App Drawer */}
      <AppDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
