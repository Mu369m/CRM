"use client";

import { useState, useEffect } from "react";
import {
  Plus,
  Trash2,
  Edit2,
  Settings,
  Users,
  Zap,
  Palette,
  Database,
  Sparkles,
} from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

interface TabConfig {
  id: string;
  label: string;
  icon: typeof Settings;
}

interface BrokerRole {
  id: string;
  name: string;
  description?: string;
}

interface BrokerFeature {
  feature_key: string;
  name: string;
  feature_type: string;
  version: string;
  status: string;
  configuration: Record<string, unknown>;
  starts_at: string | null;
  ends_at: string | null;
}

const tabs: TabConfig[] = [
  { id: "general", label: "General Settings", icon: Settings },
  { id: "roles", label: "Roles & Permissions", icon: Users },
  { id: "branding", label: "Branding", icon: Palette },
  { id: "fields", label: "Custom Fields", icon: Database },
  { id: "pipelines", label: "Pipelines", icon: Zap },
  { id: "features", label: "Features", icon: Sparkles },
];

export default function BrokerAdminPage() {
  const [activeTab, setActiveTab] = useState("general");
  const [message, setMessage] = useState("");

  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl">
        <header className="mb-8">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">
            Administration
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            Broker Configuration
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Customize your CRM instance and manage access control.
          </p>
        </header>

        {message && (
          <div className="mb-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-5">
          {/* Sidebar Navigation */}
          <aside className="rounded-lg border border-slate-800 bg-[#0D121F] p-3 lg:col-span-1">
            <div className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center gap-2 rounded-md px-3 py-2.5 text-xs font-medium transition ${
                      activeTab === tab.id
                        ? "bg-cyan-400/10 text-cyan-300"
                        : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-300"
                    }`}
                  >
                    <Icon size={14} />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </aside>

          {/* Main Content */}
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-6 lg:col-span-4">
            {activeTab === "general" && (
              <GeneralSettingsTab onMessage={setMessage} />
            )}
            {activeTab === "roles" && <RolesTab onMessage={setMessage} />}
            {activeTab === "branding" && <BrandingTab onMessage={setMessage} />}
            {activeTab === "fields" && (
              <CustomFieldsTab onMessage={setMessage} />
            )}
            {activeTab === "pipelines" && (
              <PipelinesTab onMessage={setMessage} />
            )}
            {activeTab === "features" && <FeaturesTab />}
          </div>
        </div>
      </main>
    </MainLayout>
  );
}

function FeaturesTab() {
  const [features, setFeatures] = useState<BrokerFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("access_token") ?? "";
    fetch("/api/v1/broker/features", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load enabled features.");
        return (await response.json()) as BrokerFeature[];
      })
      .then(setFeatures)
      .catch((reason: unknown) =>
        setError(
          reason instanceof Error ? reason.message : "Unable to load features.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Enabled Features</h2>
        <p className="mt-1 text-sm text-slate-400">
          Features granted to this broker by the platform owner.
        </p>
      </div>
      {loading && <p className="text-sm text-slate-500">Loading features...</p>}
      {!loading && error && (
        <div className="rounded border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          {error}
        </div>
      )}
      {!loading && !error && features.length === 0 && (
        <div className="rounded border border-slate-700 bg-slate-800/30 p-4 text-sm text-slate-400">
          No additional platform features are enabled for this broker.
        </div>
      )}
      <div className="space-y-3">
        {features.map((feature) => (
          <div
            key={feature.feature_key}
            className="flex flex-col gap-3 rounded border border-slate-700 bg-slate-800/30 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-medium text-white">{feature.name}</p>
              <p className="mt-1 text-xs text-slate-500">
                {feature.feature_key} · v{feature.version} ·{" "}
                {feature.feature_type}
              </p>
            </div>
            <span className="w-fit rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
              {feature.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function GeneralSettingsTab({
  onMessage,
}: {
  onMessage: (msg: string) => void;
}) {
  const [settings, setSettings] = useState({
    company_name: "",
    support_email: "",
    max_ib_levels: 5,
    meta_title: "",
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const response = await fetch("/api/v1/broker/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!response.ok) throw new Error("Failed to save");
      onMessage("Settings saved successfully.");
    } catch (e) {
      onMessage(
        (e instanceof Error ? e.message : "Error saving settings") + " ❌",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">General Settings</h2>

      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Company Name
          </span>
          <input
            type="text"
            value={settings.company_name}
            onChange={(e) =>
              setSettings({ ...settings, company_name: e.target.value })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            placeholder="Your Company"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Support Email
          </span>
          <input
            type="email"
            value={settings.support_email}
            onChange={(e) =>
              setSettings({ ...settings, support_email: e.target.value })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            placeholder="support@company.com"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">Page Title</span>
          <input
            type="text"
            value={settings.meta_title}
            onChange={(e) =>
              setSettings({ ...settings, meta_title: e.target.value })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            placeholder="Brokerage CRM"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Max IB Levels
          </span>
          <input
            type="number"
            min="1"
            max="10"
            value={settings.max_ib_levels}
            onChange={(e) =>
              setSettings({
                ...settings,
                max_ib_levels: parseInt(e.target.value),
              })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />
        </label>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="rounded-md bg-cyan-400 px-6 py-2.5 text-xs font-bold text-slate-950 disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Settings"}
      </button>
    </div>
  );
}

function RolesTab({ onMessage }: { onMessage: (msg: string) => void }) {
  const [roles, setRoles] = useState<BrokerRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [newRoleName, setNewRoleName] = useState("");

  useEffect(() => {
    async function loadRoles() {
      try {
        const response = await fetch("/api/v1/broker/roles", {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
        });
        if (!response.ok) throw new Error("Failed to load");
        const data = await response.json();
        setRoles(data);
      } catch {
        onMessage("Failed to load roles ❌");
      } finally {
        setLoading(false);
      }
    }
    loadRoles();
  }, [onMessage]);

  async function createRole() {
    if (!newRoleName.trim()) return;
    try {
      const response = await fetch("/api/v1/broker/roles", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ name: newRoleName }),
      });
      if (!response.ok) throw new Error("Failed to create");
      const newRole = await response.json();
      setRoles([...roles, newRole]);
      setNewRoleName("");
      onMessage("Role created successfully.");
    } catch {
      onMessage("Failed to create role ❌");
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">Roles & Permissions</h2>

      <div className="flex gap-2">
        <input
          type="text"
          value={newRoleName}
          onChange={(e) => setNewRoleName(e.target.value)}
          placeholder="New role name"
          className="flex-1 rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
        />
        <button
          onClick={createRole}
          className="rounded-md bg-emerald-400 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-500"
        >
          <Plus size={14} className="inline mr-1" /> Add Role
        </button>
      </div>

      <div className="space-y-2">
        {loading ? (
          <div className="text-center py-6 text-slate-500">
            Loading roles...
          </div>
        ) : roles.length === 0 ? (
          <div className="text-center py-6 text-slate-500">No roles yet.</div>
        ) : (
          roles.map((role) => (
            <div
              key={role.id}
              className="flex items-center justify-between rounded border border-slate-800 bg-slate-800/30 p-3"
            >
              <div>
                <p className="font-medium text-white">{role.name}</p>
                <p className="text-[10px] text-slate-500">
                  {role.description || "No description"}
                </p>
              </div>
              <div className="flex gap-1">
                <button className="p-1.5 text-slate-400 hover:text-cyan-300">
                  <Edit2 size={14} />
                </button>
                <button className="p-1.5 text-slate-400 hover:text-rose-300">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function BrandingTab({ onMessage }: { onMessage: (msg: string) => void }) {
  const [branding, setBranding] = useState({
    primary_color: "#45b69c",
    secondary_color: "#1d3430",
    logo_url: "",
    favicon_url: "",
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const response = await fetch("/api/v1/admin/branding", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(branding),
      });
      if (!response.ok) throw new Error("Failed to save");
      onMessage("Branding updated successfully.");
    } catch {
      onMessage("Failed to save branding ❌");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">
        Branding & Customization
      </h2>

      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Primary Color
          </span>
          <div className="mt-2 flex gap-2">
            <input
              type="color"
              value={branding.primary_color}
              onChange={(e) =>
                setBranding({ ...branding, primary_color: e.target.value })
              }
              className="size-12 rounded border border-slate-700 cursor-pointer"
            />
            <input
              type="text"
              value={branding.primary_color}
              onChange={(e) =>
                setBranding({ ...branding, primary_color: e.target.value })
              }
              className="flex-1 rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm font-mono text-slate-200"
            />
          </div>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Secondary Color
          </span>
          <div className="mt-2 flex gap-2">
            <input
              type="color"
              value={branding.secondary_color}
              onChange={(e) =>
                setBranding({ ...branding, secondary_color: e.target.value })
              }
              className="size-12 rounded border border-slate-700 cursor-pointer"
            />
            <input
              type="text"
              value={branding.secondary_color}
              onChange={(e) =>
                setBranding({ ...branding, secondary_color: e.target.value })
              }
              className="flex-1 rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm font-mono text-slate-200"
            />
          </div>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">Logo URL</span>
          <input
            type="url"
            value={branding.logo_url}
            onChange={(e) =>
              setBranding({ ...branding, logo_url: e.target.value })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            placeholder="https://example.com/logo.png"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-300">
            Favicon URL
          </span>
          <input
            type="url"
            value={branding.favicon_url}
            onChange={(e) =>
              setBranding({ ...branding, favicon_url: e.target.value })
            }
            className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            placeholder="https://example.com/favicon.ico"
          />
        </label>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="rounded-md bg-cyan-400 px-6 py-2.5 text-xs font-bold text-slate-950 disabled:opacity-50"
      >
        {saving ? "Saving..." : "Update Branding"}
      </button>
    </div>
  );
}

function CustomFieldsTab({ onMessage }: { onMessage: (msg: string) => void }) {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">
        Custom Fields Management
      </h2>
      <p className="text-sm text-slate-400">
        Create custom fields for Leads, Clients, and IBs
      </p>

      <div className="space-y-3">
        <div className="rounded border border-slate-700 bg-slate-800/30 p-4">
          <p className="font-medium text-white">Lead Custom Fields</p>
          <p className="mt-1 text-xs text-slate-400">
            Coming soon: Add custom fields for leads
          </p>
        </div>
        <div className="rounded border border-slate-700 bg-slate-800/30 p-4">
          <p className="font-medium text-white">Client Custom Fields</p>
          <p className="mt-1 text-xs text-slate-400">
            Coming soon: Add custom fields for clients
          </p>
        </div>
      </div>
    </div>
  );
}

function PipelinesTab({ onMessage }: { onMessage: (msg: string) => void }) {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">
        Pipeline Configuration
      </h2>
      <p className="text-sm text-slate-400">Manage CRM pipelines and stages</p>

      <div className="space-y-3">
        <div className="rounded border border-slate-700 bg-slate-800/30 p-4">
          <p className="font-medium text-white">Lead Pipeline</p>
          <p className="mt-1 text-xs text-slate-400">
            Stages: New Lead → Contacted → Interested → Qualified → Won/Lost
          </p>
        </div>
        <div className="rounded border border-slate-700 bg-slate-800/30 p-4">
          <p className="font-medium text-white">Client Pipeline</p>
          <p className="mt-1 text-xs text-slate-400">
            Stages: Prospect → KYC → Active → Trading → Inactive/Closed
          </p>
        </div>
      </div>
    </div>
  );
}
