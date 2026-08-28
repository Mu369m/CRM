"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Info, ShieldAlert, X, type LucideIcon } from "lucide-react";

type BroadcastType = "MAINTENANCE" | "URGENT_NEWS" | "INFO";

interface Broadcast {
  id: string;
  type: BroadcastType;
  message: string;
  enabled: boolean;
  target_brokers: string;
}

const dismissedKey = "crm-dismissed-broadcast";

const presentation: Record<BroadcastType, { Icon: LucideIcon; label: string; classes: string }> = {
  MAINTENANCE: { Icon: AlertTriangle, label: "Maintenance", classes: "border-amber-500/30 bg-amber-500/10 text-amber-100" },
  URGENT_NEWS: { Icon: ShieldAlert, label: "Urgent news", classes: "border-rose-500/30 bg-rose-500/10 text-rose-100" },
  INFO: { Icon: Info, label: "Information", classes: "border-sky-500/30 bg-sky-500/10 text-sky-100" },
};

export default function BroadcastBanner() {
  const [broadcast, setBroadcast] = useState<Broadcast | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const api = process.env.NEXT_PUBLIC_API_URL ?? "";

    async function loadBroadcast() {
      try {
        const response = await fetch(`${api}/api/v1/tenant/broadcast`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) return;
        const data = (await response.json()) as Broadcast | null;
        if (!data?.enabled || !data.message || !(data.type in presentation)) return;
        setBroadcast(data);
        setDismissed(window.localStorage.getItem(dismissedKey) === data.id);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) console.error("Unable to load system broadcast", error);
      }
    }

    void loadBroadcast();
    return () => controller.abort();
  }, []);

  if (!broadcast || dismissed) return null;

  const activeBroadcast = broadcast;
  const { Icon, label, classes } = presentation[activeBroadcast.type];

  function dismiss() {
    window.localStorage.setItem(dismissedKey, activeBroadcast.id);
    setDismissed(true);
  }

  return (
    <aside className={`mx-auto mb-5 flex max-w-[1440px] items-center gap-3 rounded-md border px-4 py-3 shadow-[0_8px_30px_rgba(0,0,0,0.18)] ${classes}`} role="status" aria-label={`${label} announcement`}>
      <Icon className="shrink-0" size={18} aria-hidden="true" />
      <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.16em]">{label}</span>
      <div className="min-w-0 flex-1 overflow-hidden text-xs text-slate-200">
        <div className="broadcast-marquee flex w-max min-w-full gap-12 whitespace-nowrap pr-12">
          <span>{activeBroadcast.message}</span>
          <span aria-hidden="true">{activeBroadcast.message}</span>
        </div>
      </div>
      <button type="button" onClick={dismiss} className="shrink-0 rounded p-1 text-current/70 transition hover:bg-white/10 hover:text-white" aria-label="Dismiss announcement" title="Dismiss announcement">
        <X size={16} />
      </button>
    </aside>
  );
}