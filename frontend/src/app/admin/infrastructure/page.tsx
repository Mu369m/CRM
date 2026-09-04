"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Database,
  HardDrive,
  Loader2,
  LockKeyhole,
  Save,
} from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

type Kind = "DATABASE" | "STORAGE";
type Mode = "SAAS" | "EXTERNAL";
type ProviderOption = { id: string; name: string; mode: Mode; engine?: string };

type Infrastructure = {
  mode: Mode;
  provider: string | null;
  engine: string | null;
  config_json: Record<string, string>;
  status: string;
  active: boolean;
  last_error: string | null;
  last_verified_at: string | null;
  masked_credentials: Record<string, string> | null;
};

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function InfrastructurePage() {
  const [message, setMessage] = useState("");
  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl">
        <header className="mb-8">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">
            Broker administration
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            Infrastructure
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">
            Choose independent database and file-storage services for this
            broker. Credentials stay encrypted and tenant-scoped.
          </p>
        </header>
        {message && (
          <div className="mb-5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
            {message}
          </div>
        )}
        <div className="grid gap-6 lg:grid-cols-2">
          <InfrastructureCard
            kind="DATABASE"
            icon={<Database size={18} />}
            title="Database"
            onMessage={setMessage}
          />
          <InfrastructureCard
            kind="STORAGE"
            icon={<HardDrive size={18} />}
            title="File storage"
            onMessage={setMessage}
          />
        </div>
      </main>
    </MainLayout>
  );
}

function InfrastructureCard({
  kind,
  icon,
  title,
  onMessage,
}: {
  kind: Kind;
  icon: React.ReactNode;
  title: string;
  onMessage: (message: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("SAAS");
  const [provider, setProvider] = useState("POSTGRES");
  const [config, setConfig] = useState({
    host: "",
    port: "5432",
    database: "",
    username: "",
    password: "",
  });
  const [current, setCurrent] = useState<Infrastructure | null>(null);
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const token =
    typeof window === "undefined"
      ? null
      : window.localStorage.getItem("access_token");

  useEffect(() => {
    if (!token) return;
    fetch(`${api}/api/v1/broker/infrastructure/providers?kind=${kind}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) =>
        response.ok ? (response.json() as Promise<ProviderOption[]>) : [],
      )
      .then(setProviders)
      .catch(() => onMessage(`Unable to load ${title.toLowerCase()} options.`));
    fetch(`${api}/api/v1/broker/infrastructure/${kind}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) =>
        response.ok
          ? (response.json() as Promise<Infrastructure | null>)
          : null,
      )
      .then((value) => {
        if (!value) return;
        setCurrent(value);
        setMode(value.mode);
        if (value.provider) setProvider(value.provider);
        setConfig((old) => ({
          ...old,
          host: value.config_json.host ?? old.host,
          port: value.config_json.port ?? old.port,
          database: value.config_json.database ?? old.database,
        }));
      })
      .catch(() =>
        onMessage(`Unable to load ${title.toLowerCase()} configuration.`),
      );
  }, [kind, onMessage, title, token]);

  const externalAllowed = providers.some(
    (option) => option.mode === "EXTERNAL",
  );

  const update = (key: keyof typeof config, value: string) =>
    setConfig((old) => ({ ...old, [key]: value }));
  async function save() {
    if (!token)
      return onMessage(
        "Sign in as a Broker Admin to configure infrastructure.",
      );
    setSaving(true);
    try {
      const response = await fetch(
        `${api}/api/v1/broker/infrastructure/${kind}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            mode,
            provider: mode === "SAAS" ? "SAAS" : provider,
            engine: mode === "SAAS" ? null : "POSTGRES",
            config_json:
              mode === "SAAS"
                ? {}
                : {
                    host: config.host,
                    port: config.port,
                    database: config.database,
                  },
            credentials:
              mode === "SAAS"
                ? null
                : { username: config.username, password: config.password },
          }),
        },
      );
      const data = (await response.json()) as {
        detail?: { message?: string } | string;
      };
      if (!response.ok)
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : (data.detail?.message ?? "Configuration was rejected"),
        );
      setCurrent(data as unknown as Infrastructure);
      onMessage(
        `${title} configuration verified. Activate it explicitly when ready.`,
      );
    } catch (error) {
      onMessage(
        error instanceof Error ? error.message : "Configuration failed.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function activate() {
    if (!token) return;
    setActivating(true);
    try {
      const response = await fetch(
        `${api}/api/v1/broker/infrastructure/${kind}/activate`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok)
        throw new Error("Activation requires a verified configuration.");
      setCurrent((await response.json()) as Infrastructure);
      onMessage(`${title} is now active.`);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "Activation failed.");
    } finally {
      setActivating(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-[#0D121F] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-md bg-cyan-400/10 text-cyan-300">
            {icon}
          </span>
          <div>
            <h2 className="font-semibold text-white">{title}</h2>
            <p className="mt-1 text-xs text-slate-500">
              {current?.active
                ? "Active"
                : (current?.status ?? "Not configured")}
            </p>
          </div>
        </div>
        {current?.active && (
          <CheckCircle2 className="text-emerald-400" size={20} />
        )}
      </div>
      <div className="mb-5 grid grid-cols-2 rounded-md border border-slate-800 bg-[#080D17] p-1">
        <button
          type="button"
          onClick={() => setMode("SAAS")}
          className={`rounded px-3 py-2 text-xs ${mode === "SAAS" ? "bg-cyan-400/15 text-cyan-200" : "text-slate-500"}`}
        >
          SaaS managed
        </button>
        {externalAllowed && (
          <button
            type="button"
            onClick={() => setMode("EXTERNAL")}
            className={`rounded px-3 py-2 text-xs ${mode === "EXTERNAL" ? "bg-cyan-400/15 text-cyan-200" : "text-slate-500"}`}
          >
            Own service
          </button>
        )}
      </div>
      {mode === "SAAS" ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
          Managed by the SaaS platform. No broker credentials are required.
        </div>
      ) : kind === "STORAGE" ? (
        <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-100">
          No external storage connector is enabled yet. SaaS Storage remains the
          only verified option.
        </div>
      ) : (
        <div className="space-y-3">
          <label className="block text-xs text-slate-400">
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              className="mt-2 w-full rounded border border-slate-700 bg-[#080D17] px-3 py-2 text-sm text-white"
            >
              {providers
                .filter((option) => option.mode === "EXTERNAL")
                .map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
            </select>
          </label>
          <div className="grid grid-cols-3 gap-3">
            <Field
              label="Host"
              value={config.host}
              onChange={(value) => update("host", value)}
            />
            <Field
              label="Port"
              value={config.port}
              onChange={(value) => update("port", value)}
            />
            <Field
              label="Database"
              value={config.database}
              onChange={(value) => update("database", value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Username"
              value={config.username}
              onChange={(value) => update("username", value)}
            />
            <Field
              label="Password"
              type="password"
              value={config.password}
              onChange={(value) => update("password", value)}
            />
          </div>
        </div>
      )}
      {current?.last_error && (
        <p className="mt-4 text-xs text-rose-300">{current.last_error}</p>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={saving}
          onClick={() => void save()}
          className="inline-flex items-center gap-2 rounded-md bg-cyan-400 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="animate-spin" size={14} />
          ) : (
            <Save size={14} />
          )}
          Save & test
        </button>
        {current?.status === "CONNECTED" && !current.active && (
          <button
            type="button"
            disabled={activating}
            onClick={() => void activate()}
            className="inline-flex items-center gap-2 rounded-md border border-emerald-500/40 px-4 py-2.5 text-xs font-semibold text-emerald-300 disabled:opacity-50"
          >
            {activating ? (
              <Loader2 className="animate-spin" size={14} />
            ) : (
              <LockKeyhole size={14} />
            )}
            Activate
          </button>
        )}
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="block text-xs text-slate-400">
      {label}
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded border border-slate-700 bg-[#080D17] px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
      />
    </label>
  );
}
