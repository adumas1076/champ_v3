import { useState } from "react";

const NANGO_SERVER_URL =
  import.meta.env.VITE_NANGO_SERVER_URL ||
  "https://nango-server-production-cca4.up.railway.app";

const NANGO_SECRET_KEY = import.meta.env.VITE_NANGO_SECRET_KEY || "";

interface Integration {
  id: string;
  name: string;
  icon: string;
  description: string;
  authType: "API_KEY" | "OAUTH2";
  connected: boolean;
  loading: boolean;
}

const INTEGRATIONS: Integration[] = [
  {
    id: "supabase",
    name: "Supabase",
    icon: "https://cdn.worldvectorlogo.com/logos/supabase-icon.svg",
    description: "Database, Auth & Storage",
    authType: "API_KEY",
    connected: false,
    loading: false,
  },
  {
    id: "google",
    name: "Gmail",
    icon: "https://cdn.worldvectorlogo.com/logos/gmail-icon-1.svg",
    description: "Email & Calendar",
    authType: "OAUTH2",
    connected: false,
    loading: false,
  },
  {
    id: "stripe",
    name: "Stripe",
    icon: "https://cdn.worldvectorlogo.com/logos/stripe-4.svg",
    description: "Payments & Billing",
    authType: "API_KEY",
    connected: false,
    loading: false,
  },
  {
    id: "github",
    name: "GitHub",
    icon: "https://cdn.worldvectorlogo.com/logos/github-icon-1.svg",
    description: "Code & Repositories",
    authType: "OAUTH2",
    connected: false,
    loading: false,
  },
];

export default function ConnectStack() {
  const [integrations, setIntegrations] = useState<Integration[]>(INTEGRATIONS);
  const [apiKeyModal, setApiKeyModal] = useState<string | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [userId] = useState("anthony"); // will come from auth later

  const handleConnect = async (integrationId: string) => {
    const integration = integrations.find((i) => i.id === integrationId);
    if (!integration) return;

    if (integration.authType === "API_KEY") {
      setApiKeyModal(integrationId);
      return;
    }

    // OAuth flow — future
    alert("OAuth integrations coming soon. API Key integrations work now.");
  };

  const submitApiKey = async () => {
    if (!apiKeyModal || !apiKeyInput.trim()) return;

    setIntegrations((prev) =>
      prev.map((i) =>
        i.id === apiKeyModal ? { ...i, loading: true } : i
      )
    );

    try {
      const res = await fetch(`${NANGO_SERVER_URL}/connection`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${NANGO_SECRET_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          connection_id: `${userId}-${apiKeyModal}`,
          provider_config_key: apiKeyModal,
          api_key: apiKeyInput.trim(),
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error?.message || "Connection failed");
      }

      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === apiKeyModal ? { ...i, connected: true, loading: false } : i
        )
      );
      setApiKeyModal(null);
      setApiKeyInput("");
    } catch (err: any) {
      alert(`Error: ${err.message}`);
      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === apiKeyModal ? { ...i, loading: false } : i
        )
      );
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col items-center py-16 px-4">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Connect Your Stack
        </h1>
        <p className="text-gray-500 text-lg">
          Link the tools your business runs on. One click. Fully isolated.
        </p>
      </div>

      {/* Integration Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-2xl w-full">
        {integrations.map((integration) => (
          <div
            key={integration.id}
            className={`relative border rounded-2xl p-6 flex flex-col items-center gap-4 transition-all ${
              integration.connected
                ? "border-green-400 bg-green-50"
                : "border-gray-200 bg-white hover:border-gray-400 hover:shadow-md"
            }`}
          >
            <img
              src={integration.icon}
              alt={integration.name}
              className="w-16 h-16 object-contain"
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64' fill='%23ccc'%3E%3Crect width='64' height='64' rx='12'/%3E%3Ctext x='50%25' y='55%25' text-anchor='middle' fill='white' font-size='24'%3E%3F%3C/text%3E%3C/svg%3E";
              }}
            />
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900">
                {integration.name}
              </h3>
              <p className="text-sm text-gray-500">{integration.description}</p>
            </div>

            {integration.connected ? (
              <div className="flex items-center gap-2 text-green-600 font-medium">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Connected
              </div>
            ) : (
              <button
                onClick={() => handleConnect(integration.id)}
                disabled={integration.loading}
                className="px-6 py-2.5 bg-black text-white rounded-full font-medium text-sm hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {integration.loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    Connecting...
                  </span>
                ) : (
                  "Connect"
                )}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* API Key Modal */}
      {apiKeyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <h2 className="text-xl font-bold text-gray-900 mb-2">
              Enter API Key
            </h2>
            <p className="text-gray-500 text-sm mb-6">
              Your key is encrypted and stored securely. Only your operators can
              access it.
            </p>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder="Paste your API key here..."
              className="w-full border border-gray-300 rounded-xl px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent mb-6"
              autoFocus
            />
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setApiKeyModal(null);
                  setApiKeyInput("");
                }}
                className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-full font-medium text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={submitApiKey}
                disabled={!apiKeyInput.trim()}
                className="flex-1 px-4 py-2.5 bg-black text-white rounded-full font-medium text-sm hover:bg-gray-800 disabled:opacity-30"
              >
                Connect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
