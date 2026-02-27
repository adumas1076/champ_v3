const BRAIN_URL = import.meta.env.VITE_BRAIN_URL || "http://127.0.0.1:8100";

export async function fetchHealth() {
  const res = await fetch(`${BRAIN_URL}/health`);
  return res.json();
}

export async function fetchModels() {
  const res = await fetch(`${BRAIN_URL}/v1/models`);
  return res.json();
}

export async function fetchSelfModeRuns() {
  const res = await fetch(`${BRAIN_URL}/v1/self_mode/runs`);
  return res.json();
}

export async function fetchEarsStatus() {
  const res = await fetch(`${BRAIN_URL}/v1/ears/status`);
  return res.json();
}

export async function fetchToken(room: string) {
  const res = await fetch(`${BRAIN_URL}/v1/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ room }),
  });
  return res.json();
}

export async function dispatchAgent(room: string) {
  const res = await fetch(`${BRAIN_URL}/v1/dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ room }),
  });
  return res.json();
}
