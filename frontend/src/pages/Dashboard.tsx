import { useEffect, useState } from "react";

interface DashboardProps {
  brainUrl: string;
}

interface HealthData {
  status: string;
  service: string;
  phase: number;
  memory: boolean;
}

interface ModelData {
  id: string;
  owned_by: string;
}

interface SelfModeRun {
  id: string;
  status: string;
  current_step: string;
  created_at: string;
  updated_at: string;
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${
        ok ? "bg-champ-green" : "bg-champ-red"
      }`}
    />
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-champ-card border border-champ-border rounded-lg p-5">
      <h2 className="text-sm font-semibold text-champ-muted uppercase tracking-wide mb-3">
        {title}
      </h2>
      {children}
    </div>
  );
}

export default function Dashboard({ brainUrl }: DashboardProps) {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [models, setModels] = useState<ModelData[]>([]);
  const [runs, setRuns] = useState<SelfModeRun[]>([]);
  const [ears, setEars] = useState<{ ears: string } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [hRes, mRes, rRes, eRes] = await Promise.allSettled([
          fetch(`${brainUrl}/health`).then((r) => r.json()),
          fetch(`${brainUrl}/v1/models`).then((r) => r.json()),
          fetch(`${brainUrl}/v1/self_mode/runs`).then((r) => r.json()),
          fetch(`${brainUrl}/v1/ears/status`).then((r) => r.json()),
        ]);

        if (hRes.status === "fulfilled") setHealth(hRes.value);
        if (mRes.status === "fulfilled") setModels(mRes.value.data || []);
        if (rRes.status === "fulfilled") setRuns(rRes.value.runs || []);
        if (eRes.status === "fulfilled") setEars(eRes.value);

        setError("");
      } catch (e) {
        setError(`Failed to reach Brain at ${brainUrl}`);
      }
    };

    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [brainUrl]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">System Dashboard</h1>

      {error && (
        <div className="bg-champ-red/10 border border-champ-red/30 text-champ-red rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Brain Health */}
        <Card title="Brain">
          {health ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <StatusDot ok={health.status === "ok"} />
                <span className="font-medium">
                  {health.status === "ok" ? "Online" : "Unhealthy"}
                </span>
              </div>
              <div className="text-sm text-champ-muted">
                Phase {health.phase} | Memory:{" "}
                {health.memory ? "connected" : "disconnected"}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <StatusDot ok={false} />
              <span className="text-champ-muted">Offline</span>
            </div>
          )}
        </Card>

        {/* LLM Models */}
        <Card title="LLM Models">
          {models.length > 0 ? (
            <ul className="space-y-1.5">
              {models.map((m) => (
                <li key={m.id} className="flex items-center gap-2 text-sm">
                  <StatusDot ok={true} />
                  <span className="font-mono">{m.id}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-champ-muted">No models loaded</p>
          )}
        </Card>

        {/* Ears */}
        <Card title="Ears (Wake Word)">
          <div className="flex items-center gap-2">
            <StatusDot ok={ears?.ears === "online"} />
            <span className="font-medium">
              {ears?.ears === "online"
                ? "Listening"
                : ears?.ears === "offline"
                ? "Offline (local only)"
                : "Unknown"}
            </span>
          </div>
          <p className="text-xs text-champ-muted mt-1">
            Ears requires local mic hardware
          </p>
        </Card>
      </div>

      {/* Self Mode Runs */}
      <Card title="Self Mode Runs">
        {runs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-champ-muted text-left border-b border-champ-border">
                  <th className="pb-2 pr-4">Run ID</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Step</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b border-champ-border/50">
                    <td className="py-2 pr-4 font-mono text-xs">{run.id}</td>
                    <td className="py-2 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          run.status === "complete"
                            ? "bg-champ-green/20 text-champ-green"
                            : run.status === "failed"
                            ? "bg-champ-red/20 text-champ-red"
                            : run.status === "executing"
                            ? "bg-champ-accent/20 text-champ-accent"
                            : "bg-champ-yellow/20 text-champ-yellow"
                        }`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-champ-muted">
                      {run.current_step || "-"}
                    </td>
                    <td className="py-2 text-champ-muted">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-champ-muted">No runs yet</p>
        )}
      </Card>
    </div>
  );
}
