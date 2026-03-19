import { Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import VoiceCall from "./pages/VoiceCall";
import AvatarLab from "./pages/AvatarLab";
import CocreatiqHome from "./pages/CocreatiqHome";

const BRAIN_URL = import.meta.env.VITE_BRAIN_URL || "http://127.0.0.1:8100";

function Nav() {
  const location = useLocation();

  // Hide nav on full-screen pages
  if (location.pathname === "/call" || location.pathname === "/avatar-lab" || location.pathname === "/cocreatiq") return null;

  const isActive = (path: string) =>
    location.pathname === path
      ? "text-white border-champ-accent"
      : "text-champ-muted border-transparent hover:text-white";

  return (
    <nav className="border-b border-champ-border px-6 py-3 flex items-center gap-6">
      <span className="text-lg font-bold tracking-tight">CHAMP V3</span>
      <Link
        to="/"
        className={`text-sm border-b-2 pb-1 transition-colors ${isActive("/")}`}
      >
        Dashboard
      </Link>
      <Link
        to="/call"
        className={`text-sm border-b-2 pb-1 transition-colors ${isActive("/call")}`}
      >
        Voice Call
      </Link>
    </nav>
  );
}

export default function App() {
  const location = useLocation();
  const isFullScreen = location.pathname === "/call" || location.pathname === "/avatar-lab" || location.pathname === "/cocreatiq";

  return (
    <div className="min-h-screen bg-champ-bg text-white">
      <Nav />
      {isFullScreen ? (
        <Routes>
          <Route path="/call" element={<VoiceCall brainUrl={BRAIN_URL} />} />
          <Route path="/avatar-lab" element={<AvatarLab />} />
        </Routes>
      ) : (
        <main className="p-6 max-w-5xl mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard brainUrl={BRAIN_URL} />} />
            <Route path="/call" element={<VoiceCall brainUrl={BRAIN_URL} />} />
          </Routes>
        </main>
      )}
    </div>
  );
}
