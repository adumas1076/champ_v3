import { useState, useEffect } from "react";

const NANGO_SERVER_URL =
  import.meta.env.VITE_NANGO_SERVER_URL ||
  "https://nango-server-production-cca4.up.railway.app";

const NANGO_SECRET_KEY = import.meta.env.VITE_NANGO_SECRET_KEY || "";

interface Integration {
  id: string;
  nangoKey: string;
  name: string;
  icon: string;
  description: string;
  connected: boolean;
  loading: boolean;
}

const INTEGRATIONS: Integration[] = [
  {
    id: "supabase",
    nangoKey: "supabase-oauth",
    name: "Supabase",
    icon: "https://cdn.worldvectorlogo.com/logos/supabase-icon.svg",
    description: "Database, Auth & Storage",
    connected: false,
    loading: false,
  },
  {
    id: "google",
    nangoKey: "google",
    name: "Gmail",
    icon: "https://cdn.worldvectorlogo.com/logos/gmail-icon-1.svg",
    description: "Email & Calendar",
    connected: false,
    loading: false,
  },
  {
    id: "stripe",
    nangoKey: "stripe",
    name: "Stripe",
    icon: "https://cdn.worldvectorlogo.com/logos/stripe-4.svg",
    description: "Payments & Billing",
    connected: false,
    loading: false,
  },
  {
    id: "github",
    nangoKey: "github-oauth",
    name: "GitHub",
    icon: "https://cdn.worldvectorlogo.com/logos/github-icon-1.svg",
    description: "Code & Repositories",
    connected: false,
    loading: false,
  },
];

export default function ConnectStack() {
  const [integrations, setIntegrations] = useState<Integration[]>(INTEGRATIONS);
  const [userId] = useState("anthony"); // will come from auth later

  // Check URL params for OAuth callback result
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("success") === "true") {
      const provider = params.get("provider");
      if (provider) {
        setIntegrations((prev) =>
          prev.map((i) =>
            i.nangoKey === provider ? { ...i, connected: true } : i
          )
        );
      }
      window.history.replaceState({}, "", "/connect");
    }
  }, []);

  const handleConnect = async (integration: Integration) => {
    setIntegrations((prev) =>
      prev.map((i) =>
        i.id === integration.id ? { ...i, loading: true } : i
      )
    );

    try {
      // Step 1: Create a connect session token from our backend
      const sessionRes = await fetch(`${NANGO_SERVER_URL}/connect/sessions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${NANGO_SECRET_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          end_user: {
            id: userId,
            email: "adumas1076@gmail.com",
            display_name: "Anthony",
          },
        }),
      });

      if (!sessionRes.ok) {
        const err = await sessionRes.json();
        throw new Error(err.error?.message || "Failed to create session");
      }

      const session = await sessionRes.json();
      const token = session.data.token;

      // Step 2: Redirect to Nango's OAuth flow with the session token
      const authUrl =
        `${NANGO_SERVER_URL}/oauth/connect/${integration.nangoKey}` +
        `?connect_session_token=${encodeURIComponent(token)}`;

      window.location.href = authUrl;
    } catch (err: any) {
      alert(`Error: ${err.message}`);
      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === integration.id ? { ...i, loading: false } : i
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
                onClick={() => handleConnect(integration)}
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
    </div>
  );
}
