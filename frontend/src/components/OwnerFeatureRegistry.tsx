"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Plus, RefreshCw } from "lucide-react";

interface Feature {
  id: string;
  feature_key: string;
  name: string;
  feature_type: string;
  version: string;
  is_available: boolean;
  eligible_plans: string[];
  pricing_type: string;
  configuration_schema: Record<string, unknown>;
  internal_notes: string | null;
}

interface Grant {
  id: string;
  tenant_id: string;
  feature_id: string;
  status: string;
  configuration: Record<string, unknown>;
  starts_at: string | null;
  ends_at: string | null;
}

interface BrokerSummary {
  id: string;
  name: string;
  plan: string;
  is_active: boolean;
}

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function OwnerFeatureRegistry() {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [brokers, setBrokers] = useState<BrokerSummary[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [featureForm, setFeatureForm] = useState({
    feature_key: "",
    name: "",
    feature_type: "MODULE",
    version: "1.0",
    eligible_plans: "",
    pricing_type: "INCLUDED",
  });
  const [grantForm, setGrantForm] = useState({
    feature_id: "",
    tenant_id: "",
    status: "ENABLED",
    starts_at: "",
    ends_at: "",
    configuration: "{}",
  });

  const selectedFeature = features.find(
    (feature) => feature.id === grantForm.feature_id,
  );

  async function loadFeatures() {
    setLoading(true);
    try {
      const response = await fetch(`${api}/api/v1/owner/features`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
      });
      if (!response.ok) throw new Error("Unable to load feature registry.");
      setFeatures((await response.json()) as Feature[]);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load feature registry.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadBrokers() {
    try {
      const response = await fetch(`${api}/api/v1/owner/features/brokers`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
      });
      if (!response.ok) throw new Error("Unable to load broker directory.");
      setBrokers((await response.json()) as BrokerSummary[]);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to load brokers.",
      );
    }
  }

  useEffect(() => {
    void loadFeatures();
    void loadBrokers();
  }, []);

  async function createFeature(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const response = await fetch(`${api}/api/v1/owner/features`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
        body: JSON.stringify({
          ...featureForm,
          eligible_plans: featureForm.eligible_plans
            .split(",")
            .map((plan) => plan.trim().toUpperCase())
            .filter(Boolean),
        }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      if (!response.ok)
        throw new Error(data.detail ?? "Feature creation failed.");
      setFeatureForm({
        feature_key: "",
        name: "",
        feature_type: "MODULE",
        version: "1.0",
        eligible_plans: "",
        pricing_type: "INCLUDED",
      });
      setMessage("Feature registered successfully.");
      await loadFeatures();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Feature creation failed.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function grantFeature(event: FormEvent) {
    event.preventDefault();
    if (!grantForm.feature_id || !grantForm.tenant_id)
      return setMessage("Feature and tenant ID are required.");
    let configuration: Record<string, unknown>;
    try {
      configuration = JSON.parse(grantForm.configuration) as Record<
        string,
        unknown
      >;
      if (!configuration || Array.isArray(configuration))
        throw new Error("Configuration must be a JSON object.");
    } catch (error) {
      return setMessage(
        error instanceof Error ? error.message : "Invalid JSON configuration.",
      );
    }
    setSaving(true);
    try {
      const response = await fetch(
        `${api}/api/v1/owner/features/${grantForm.feature_id}/grants`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
          },
          body: JSON.stringify({
            tenant_id: grantForm.tenant_id,
            status: grantForm.status,
            configuration,
            starts_at: grantForm.starts_at
              ? new Date(grantForm.starts_at).toISOString()
              : null,
            ends_at: grantForm.ends_at
              ? new Date(grantForm.ends_at).toISOString()
              : null,
          }),
        },
      );
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      if (!response.ok) throw new Error(data.detail ?? "Feature grant failed.");
      setMessage("Feature grant saved and audited.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Feature grant failed.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-8 rounded-xl border border-slate-800 bg-[#0D121F] p-6 text-slate-100">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">
            Owner control
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            Feature registry
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Register reusable platform features and grant them to isolated
            broker tenants without changing their plans.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadFeatures()}
          className="inline-flex items-center gap-2 rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-300"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      {message && (
        <p className="mt-4 rounded border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-200">
          {message}
        </p>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <form
          onSubmit={createFeature}
          className="space-y-3 rounded-lg border border-slate-800 bg-[#080D17] p-4"
        >
          <h3 className="font-medium text-white">Register feature</h3>
          <Input
            label="Feature key"
            value={featureForm.feature_key}
            placeholder="advanced_reporting"
            onChange={(value) =>
              setFeatureForm({ ...featureForm, feature_key: value })
            }
          />
          <Input
            label="Display name"
            value={featureForm.name}
            placeholder="Advanced Reporting"
            onChange={(value) =>
              setFeatureForm({ ...featureForm, name: value })
            }
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Type"
              value={featureForm.feature_type}
              onChange={(value) =>
                setFeatureForm({ ...featureForm, feature_type: value })
              }
            />
            <Input
              label="Version"
              value={featureForm.version}
              onChange={(value) =>
                setFeatureForm({ ...featureForm, version: value })
              }
            />
          </div>
          <Input
            label="Eligible plans (comma separated)"
            value={featureForm.eligible_plans}
            placeholder="ENTERPRISE, PROFESSIONAL"
            onChange={(value) =>
              setFeatureForm({ ...featureForm, eligible_plans: value })
            }
          />
          <button
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md bg-cyan-400 px-4 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
          >
            <Plus size={14} /> Register feature
          </button>
        </form>
        <form
          onSubmit={grantFeature}
          className="space-y-3 rounded-lg border border-slate-800 bg-[#080D17] p-4"
        >
          <h3 className="font-medium text-white">Grant to broker</h3>
          <label className="block text-xs text-slate-400">
            Feature
            <select
              required
              value={grantForm.feature_id}
              onChange={(event) =>
                setGrantForm({ ...grantForm, feature_id: event.target.value })
              }
              className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white"
            >
              <option value="">Select feature</option>
              {features.map((feature) => (
                <option key={feature.id} value={feature.id}>
                  {feature.name} ({feature.feature_key})
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs text-slate-400">
              Starts at
              <input
                type="datetime-local"
                value={grantForm.starts_at}
                onChange={(event) =>
                  setGrantForm({ ...grantForm, starts_at: event.target.value })
                }
                className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="block text-xs text-slate-400">
              Ends at
              <input
                type="datetime-local"
                value={grantForm.ends_at}
                onChange={(event) =>
                  setGrantForm({ ...grantForm, ends_at: event.target.value })
                }
                className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white"
              />
            </label>
          </div>
          <label className="block text-xs text-slate-400">
            Feature configuration (JSON)
            <textarea
              value={grantForm.configuration}
              onChange={(event) =>
                setGrantForm({
                  ...grantForm,
                  configuration: event.target.value,
                })
              }
              rows={4}
              className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 font-mono text-xs text-white"
              aria-describedby="feature-schema-hint"
            />
          </label>
          <p id="feature-schema-hint" className="text-xs text-slate-500">
            {selectedFeature?.configuration_schema &&
            Object.keys(selectedFeature.configuration_schema).length > 0
              ? `Schema: ${JSON.stringify(selectedFeature.configuration_schema)}`
              : "No feature-specific configuration schema."}
          </p>
          <label className="block text-xs text-slate-400">
            Broker tenant
            <select
              required
              value={grantForm.tenant_id}
              onChange={(event) =>
                setGrantForm({ ...grantForm, tenant_id: event.target.value })
              }
              className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white"
            >
              <option value="">Select broker</option>
              {brokers.map((broker) => (
                <option
                  key={broker.id}
                  value={broker.id}
                  disabled={!broker.is_active}
                >
                  {broker.name} · {broker.plan} ·{" "}
                  {broker.is_active ? "Active" : "Inactive"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-400">
            Status
            <select
              value={grantForm.status}
              onChange={(event) =>
                setGrantForm({ ...grantForm, status: event.target.value })
              }
              className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white"
            >
              <option>ENABLED</option>
              <option>TRIAL</option>
              <option>DISABLED</option>
              <option>SUSPENDED</option>
            </select>
          </label>
          <button
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-400 px-4 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
          >
            <Check size={14} /> Save grant
          </button>
        </form>
      </div>
      <div className="mt-6 space-y-2">
        {loading ? (
          <p className="text-sm text-slate-500">Loading registry...</p>
        ) : features.length === 0 ? (
          <p className="text-sm text-slate-500">No features registered.</p>
        ) : (
          features.map((feature) => (
            <div
              key={feature.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded border border-slate-800 px-4 py-3"
            >
              <div>
                <p className="font-medium text-white">{feature.name}</p>
                <p className="text-xs text-slate-500">
                  {feature.feature_key} · v{feature.version} ·{" "}
                  {feature.pricing_type}
                </p>
              </div>
              <span className="text-xs text-emerald-300">
                {feature.is_available ? "Available" : "Unavailable"}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function Input({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs text-slate-400">
      {label}
      <input
        required
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded border border-slate-700 bg-[#0D121F] px-3 py-2 text-sm text-white placeholder:text-slate-600"
      />
    </label>
  );
}
