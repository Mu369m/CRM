"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useTenant } from "@/context/TenantContext";

type Tab = "branding" | "ib" | "mt";

interface SettingsForm {
  primary_color: string;
  secondary_color: string;
  meta_title: string;
  support_email: string;
  logo_url: string;
  favicon_url: string;
  max_ib_levels: number;
  tenant_schema: string;
}

const emptySettings: SettingsForm = { primary_color: "#45b69c", secondary_color: "#1d3430", meta_title: "My Brokerage", support_email: "", logo_url: "", favicon_url: "", max_ib_levels: 5, tenant_schema: "tenant_00000000_0000_0000_0000_000000000000" };

export default function AdminSettingsPage() {
  const { branding } = useTenant();
  const [activeTab, setActiveTab] = useState<Tab>("branding");
  const [settings, setSettings] = useState<SettingsForm>({ ...emptySettings, meta_title: branding?.companyName ?? emptySettings.meta_title });
  const [ib, setIb] = useState({ instrument_group: "Forex", strategy: "PER_LOT_FIXED", level: 1, fixed_per_lot: "8", spread_percentage: "0", asset_class: "FOREX", enabled: true });
  const [mt, setMt] = useState({ platform: "MT5", name: "MT5-Live-Server-01", server: "", login: "", username: "", password: "", enabled: true });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const token = typeof window === "undefined" ? "" : window.localStorage.getItem("access_token") ?? "";

  useEffect(() => {
    if (!branding) return;
    const timer = window.setTimeout(() => setSettings((current) => ({ ...current, meta_title: branding.companyName || current.meta_title, primary_color: branding.primaryColor, secondary_color: branding.secondaryColor, logo_url: branding.logoUrl ?? "" })), 0);
    return () => window.clearTimeout(timer);
  }, [branding]);

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setMessage("");
    const endpoint = activeTab === "branding" ? "/api/settings" : activeTab === "ib" ? "/api/admin/rebate-rules" : "/api/admin/manager-connections";
    const body = activeTab === "branding" ? settings : activeTab === "ib" ? { ...ib, level: Number(ib.level), fixed_per_lot: Number(ib.fixed_per_lot), spread_percentage: Number(ib.spread_percentage) } : mt;
    try {
      const response = await fetch(`${api}${endpoint}`, { method: activeTab === "branding" || activeTab === "ib" ? "PUT" : "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Request failed");
      setMessage(activeTab === "branding" ? "Branding applied live." : activeTab === "ib" ? "IB rebate rule saved." : "Manager credentials encrypted and saved.");
      if (activeTab === "mt") setMt((current) => ({ ...current, password: "" }));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save configuration."); } finally { setSaving(false); }
  }

  return <main className="settings-page"><header className="settings-header"><div><button className="back-button" type="button" onClick={() => window.history.back()}><span className="button-arrow" aria-hidden="true">←</span> Back</button><p className="eyebrow" style={{ marginTop: 16 }}>Admin back-office</p><h1>Broker Control Center</h1><p className="settings-subtitle">Runtime configuration for branding, multi-tier rebates, and trading server links.</p></div><span className="settings-status">{message || "Changes require authorization"}</span></header><div className="settings-tabs">{(["branding", "ib", "mt"] as Tab[]).map((tab) => <button className={activeTab === tab ? "settings-tab active" : "settings-tab"} onClick={() => { setActiveTab(tab); setMessage(""); }} key={tab}>{tab === "branding" ? "Dynamic Branding & UI" : tab === "ib" ? "Multi-Tier IB Rebates" : "MT4 / MT5 Connectors"}</button>)}</div><form onSubmit={save} className="settings-form">
  {activeTab === "branding" && <section className="settings-card"><p className="eyebrow">Tenant skinning</p><h2>Brand identity & color tokens</h2><label>Company / broker name<input value={settings.meta_title} onChange={(event) => setSettings({ ...settings, meta_title: event.target.value })} required /></label><label>Support email<input type="email" value={settings.support_email} onChange={(event) => setSettings({ ...settings, support_email: event.target.value })} /></label><div className="color-fields"><label>Primary color<input type="color" value={settings.primary_color} onChange={(event) => setSettings({ ...settings, primary_color: event.target.value })} /></label><label>Secondary color<input type="color" value={settings.secondary_color} onChange={(event) => setSettings({ ...settings, secondary_color: event.target.value })} /></label></div><label>Logo image URL<input type="url" value={settings.logo_url} onChange={(event) => setSettings({ ...settings, logo_url: event.target.value })} placeholder="https://broker.example/logo.png" /></label></section>}
  {activeTab === "ib" && <section className="settings-card"><p className="eyebrow">Revenue engine</p><h2>Configure commission hierarchy</h2><label>Instrument group<input value={ib.instrument_group} onChange={(event) => setIb({ ...ib, instrument_group: event.target.value })} required /></label><label>Payout model<select value={ib.strategy} onChange={(event) => setIb({ ...ib, strategy: event.target.value })}><option value="PER_LOT_FIXED">Fixed amount per lot</option><option value="PERCENTAGE_SPREAD">Percentage of spread</option><option value="ASSET_BASED">Asset based</option></select></label><div className="ib-row"><label>Tier<input type="number" min="1" max={settings.max_ib_levels} value={ib.level} onChange={(event) => setIb({ ...ib, level: Number(event.target.value) })} /></label><label>Fixed / lot<input type="number" min="0" step="0.01" value={ib.fixed_per_lot} onChange={(event) => setIb({ ...ib, fixed_per_lot: event.target.value })} /></label><label>Spread %<input type="number" min="0" max="100" step="0.01" value={ib.spread_percentage} onChange={(event) => setIb({ ...ib, spread_percentage: event.target.value })} /></label></div><div className="rule-callout">Up to {settings.max_ib_levels} levels · tenant scoped · journaled on payout</div></section>}
  {activeTab === "mt" && <section className="settings-card"><p className="eyebrow">Platform manager</p><h2>Link trading server</h2><label>Server display name<input value={mt.name} onChange={(event) => setMt({ ...mt, name: event.target.value })} required /></label><div className="ib-row"><label>Platform<select value={mt.platform} onChange={(event) => setMt({ ...mt, platform: event.target.value })}><option>MT5</option><option>MT4</option><option>CTRADER</option></select></label><label>Manager host:port<input value={mt.server} onChange={(event) => setMt({ ...mt, server: event.target.value })} placeholder="manager.example.com:443" required /></label></div><div className="ib-row"><label>Manager login<input value={mt.login} onChange={(event) => setMt({ ...mt, login: event.target.value })} required /></label><label>Username (optional)<input value={mt.username} onChange={(event) => setMt({ ...mt, username: event.target.value })} /></label></div><label>Manager password<input type="password" value={mt.password} onChange={(event) => setMt({ ...mt, password: event.target.value })} required /><small className="field-help">Encrypted with AES-256-GCM before storage. Credentials are never returned by the API.</small></label></section>}
  <div className="settings-actions"><Link className="cancel-link" href="/">Back to overview</Link><button className="save-button" disabled={saving} type="submit">{saving ? "Saving..." : activeTab === "mt" ? "Encrypt & connect" : "Apply configuration"}</button></div></form></main>;
}