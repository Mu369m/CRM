"use client";

import { useEffect, useState } from "react";
import { Check, ExternalLink, FileCheck2, X } from "lucide-react";

interface LatestPolicy { id: string; version: string; title: string; summary: string; }
export function AcceptTermsModal({ open, onAccepted, onClose }: { open: boolean; onAccepted: () => void; onClose?: () => void }) {
  const [policy, setPolicy] = useState<LatestPolicy | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void fetch("/api/v1/legal/latest", { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<LatestPolicy> : Promise.reject(new Error("Latest policy unavailable")))
      .then(setPolicy)
      .catch((cause: unknown) => { if (!(cause instanceof DOMException && cause.name === "AbortError")) setError("Latest policy could not be loaded."); });
    return () => controller.abort();
  }, [open]);
  if (!open) return null;
  async function accept() { if (!agreed) return; setSaving(true); setError(""); try { const response = await fetch("/api/v1/legal/acceptance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ policy_id: policy?.id, version_id: policy?.version, accepted_at: new Date().toISOString(), user_ip: "server-resolved" }) }); if (!response.ok) throw new Error("Acceptance could not be recorded"); onAccepted(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Acceptance could not be recorded"); } finally { setSaving(false); } }
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4 backdrop-blur-sm"><section className="w-full max-w-lg rounded-lg border border-slate-700 bg-[#0D121F] p-6 shadow-2xl"><div className="flex items-start justify-between"><div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-md bg-cyan-400/10 text-cyan-300"><FileCheck2 size={19} /></span><div><p className="text-[10px] uppercase tracking-widest text-cyan-400">Required action</p><h2 className="mt-1 text-lg font-semibold text-white">Review latest legal terms</h2></div></div>{onClose && <button className="text-slate-500 hover:text-white" onClick={onClose} aria-label="Close"><X size={18} /></button>}</div><p className="mt-6 text-sm leading-6 text-slate-400">Access requires acceptance of the latest Terms of Service and Privacy Policy. Your acceptance timestamp and policy version are recorded for audit purposes.</p><div className="mt-5 rounded-md border border-slate-800 bg-[#070A11] p-4"><p className="text-xs font-semibold text-white">Northstar legal framework <span className="ml-2 text-cyan-300">v2.1</span></p><p className="mt-2 text-xs leading-5 text-slate-500">Includes data sovereignty, AES-256 vault controls, subscription rules, and service availability commitments.</p><a className="mt-3 inline-flex items-center gap-1 text-xs text-cyan-300" href="/terms" target="_blank">Read full terms <ExternalLink size={12} /></a></div><label className="mt-5 flex items-start gap-3 text-xs leading-5 text-slate-300"><input className="mt-1" type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} /><span>I agree to the latest Terms of Service, Privacy Policy, DPA, and SLA.</span></label>{error && <p className="mt-3 text-xs text-rose-300">{error}</p>}<button className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40" disabled={!agreed || saving} onClick={() => void accept()}>{saving ? "Recording acceptance..." : <><Check size={16} /> Accept and continue</>}</button></section></div>;
}