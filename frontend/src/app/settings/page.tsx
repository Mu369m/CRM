"use client";

import { FormEvent, useState } from "react";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ primary_color: "#45b69c", secondary_color: "#1d3430", meta_title: "Northstar Markets", support_email: "support@northstar.example", max_ib_levels: 5, tenant_schema: "tenant_00000000_0000_0000_0000_000000000000", logo_url: "", favicon_url: "" });
  const update = (key: string, value: string | number) => setForm((current) => ({ ...current, [key]: value }));

  async function save(event: FormEvent) {
    event.preventDefault();
    const token = window.localStorage.getItem("access_token");
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(form) });
    setSaved(response.ok);
  }

  return <main className="settings-page"><div className="settings-header"><div><p className="eyebrow">Admin back-office</p><h1>Tenant settings</h1><p className="settings-subtitle">Control the client experience and revenue rules without a deployment.</p></div><span className="settings-status">{saved ? "Saved just now" : "Unsaved changes"}</span></div><form onSubmit={save} className="settings-grid"><section className="settings-card"><p className="eyebrow">Branding & domain</p><h2>Tenant identity</h2><label>Meta title<input value={form.meta_title} onChange={(event) => update("meta_title", event.target.value)} /></label><label>Support email<input type="email" value={form.support_email} onChange={(event) => update("support_email", event.target.value)} /></label><label>Logo URL<input value={form.logo_url} onChange={(event) => update("logo_url", event.target.value)} /></label><div className="color-fields"><label>Primary color<input type="color" value={form.primary_color} onChange={(event) => update("primary_color", event.target.value)} /></label><label>Secondary color<input type="color" value={form.secondary_color} onChange={(event) => update("secondary_color", event.target.value)} /></label></div></section><section className="settings-card"><p className="eyebrow">IB network</p><h2>Revenue configuration</h2><label>Maximum rebate levels<input type="number" min="1" max="100" value={form.max_ib_levels} onChange={(event) => update("max_ib_levels", Number(event.target.value))} /></label><div className="rule-preview"><span className="rule-dot" /><div><strong>Runtime rule engine</strong><small>PER_LOT_FIXED · PERCENTAGE_SPREAD · ASSET_BASED</small></div></div><div className="rule-preview"><span className="rule-dot blue-dot" /><div><strong>KYC requirement matrix</strong><small>Country-aware document requirements</small></div></div><div className="rule-preview"><span className="rule-dot gold-dot" /><div><strong>Deposit bonus rules</strong><small>Equity credit and withdrawal lot targets</small></div></div></section><div className="settings-actions"><a href="/" className="cancel-link">Back to overview</a><button className="save-button" type="submit">Save configuration</button></div></form></main>;
}
