"use client";

import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, RefreshCw, ShieldAlert, SlidersHorizontal, X } from "lucide-react";

type Side = "BUY" | "SELL";
type Position = {
  id: string;
  trader_id: string;
  account_id: string;
  symbol: string;
  volume: string;
  side: Side;
  open_price: string;
  current_price: string;
  floating_pnl: string;
  opened_at: string;
  status: "OPEN" | "CLOSED";
};
type Exposure = { symbol: string; total_buy_lots: string; total_sell_lots: string; net_volume: string };
type RiskAccount = { account_id: string; trader_id: string; equity: string; margin_usage_percent: string };
type RiskMetrics = { total_equity: string; total_floating_pnl: string; margin_usage_percent: string; accounts_at_risk_stop_out: number; high_risk_accounts: RiskAccount[] };
type RiskRule = { id?: string; max_leverage: number; margin_call_level: string; stop_out_level: string; max_lot_size: string; prohibited_symbols_json: string[]; max_drawdown_alert: string };
type PositionPage = { items: Position[]; total: number };

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default function RiskDashboard() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [exposure, setExposure] = useState<Exposure[]>([]);
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [rules, setRules] = useState<RiskRule>({ max_leverage: 500, margin_call_level: "100", stop_out_level: "50", max_lot_size: "100", prohibited_symbols_json: [], max_drawdown_alert: "20" });
  const [symbol, setSymbol] = useState("ALL");
  const [account, setAccount] = useState("");
  const [side, setSide] = useState<Side | "ALL">("ALL");
  const [message, setMessage] = useState("Loading risk feed...");
  const [savingRules, setSavingRules] = useState(false);
  const [closingId, setClosingId] = useState<string | null>(null);
  const token = typeof window === "undefined" ? "" : window.localStorage.getItem("access_token") ?? "";
  const headers = { Authorization: `Bearer ${token}` };

  async function loadRisk() {
    try {
      const [positionsResponse, exposureResponse, metricsResponse, rulesResponse] = await Promise.all([
        fetch(`${api}/api/v1/broker/risk/positions?limit=200`, { headers }),
        fetch(`${api}/api/v1/broker/risk/exposure`, { headers }),
        fetch(`${api}/api/v1/broker/risk/metrics`, { headers }),
        fetch(`${api}/api/v1/broker/risk/rules`, { headers }),
      ]);
      if (!positionsResponse.ok || !exposureResponse.ok || !metricsResponse.ok) throw new Error("Risk feed unavailable.");
      const positionPage = await positionsResponse.json() as PositionPage;
      setPositions(positionPage.items);
      setExposure(await exposureResponse.json() as Exposure[]);
      setMetrics(await metricsResponse.json() as RiskMetrics);
      if (rulesResponse.ok) {
        const savedRules = await rulesResponse.json() as RiskRule | null;
        if (savedRules) setRules(savedRules);
      }
      setMessage(`Updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Risk feed unavailable.");
    }
  }

  useEffect(() => {
    void loadRisk();
    const timer = window.setInterval(() => void loadRisk(), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  async function forceClose(position: Position) {
    setClosingId(position.id);
    try {
      const response = await fetch(`${api}/api/v1/broker/risk/positions/${position.id}/close`, { method: "POST", headers });
      const data = await response.json().catch(() => ({})) as { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Force close failed.");
      setMessage("Position force-closed and added to trade history.");
      await loadRisk();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Force close failed.");
    } finally {
      setClosingId(null);
    }
  }

  async function saveRules(event: FormEvent) {
    event.preventDefault();
    setSavingRules(true);
    try {
      const response = await fetch(`${api}/api/v1/broker/risk/rules`, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(rules) });
      const data = await response.json().catch(() => ({})) as RiskRule & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Risk rules could not be saved.");
      setRules(data);
      setMessage("Risk limits saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Risk rules could not be saved.");
    } finally {
      setSavingRules(false);
    }
  }

  const visiblePositions = positions.filter((position) => (symbol === "ALL" || position.symbol === symbol) && (!account || position.account_id.toLowerCase().includes(account.toLowerCase())) && (side === "ALL" || position.side === side));
  const maxExposure = Math.max(...exposure.map((row) => Math.max(Number(row.total_buy_lots), Number(row.total_sell_lots))), 1);

  return <main className="min-h-screen bg-[#070A11] px-4 py-7 text-slate-100 sm:px-6 lg:px-8"><div className="mx-auto max-w-7xl"><header className="mb-7 flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-end"><div><p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.2em] text-cyan-400"><ShieldAlert size={13} /> Broker risk desk</p><h1 className="mt-2 text-3xl font-semibold text-white">Positions & risk monitoring</h1><p className="mt-2 text-sm text-slate-500">Live position exposure, floating P&L, and account-level margin pressure.</p></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">{message}</span><button type="button" onClick={() => void loadRisk()} className="inline-flex items-center gap-2 rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-cyan-400/50"><RefreshCw size={14} /> Refresh</button></div></header><div className="mb-5 grid gap-4 sm:grid-cols-3"><Metric label="Total open lots" value={positions.reduce((sum, position) => sum + Number(position.volume), 0).toFixed(2)} detail={`${positions.length} active positions`} /><Metric label="Net floating P&L" value={money.format(Number(metrics?.total_floating_pnl ?? 0))} detail={`${Number(metrics?.margin_usage_percent ?? 0).toFixed(2)}% derived margin usage`} tone={Number(metrics?.total_floating_pnl ?? 0) >= 0 ? "positive" : "negative"} /><Metric label="Accounts near stop-out" value={String(metrics?.accounts_at_risk_stop_out ?? 0)} detail={`${metrics?.high_risk_accounts.length ?? 0} high-risk accounts`} tone={(metrics?.accounts_at_risk_stop_out ?? 0) > 0 ? "negative" : "positive"} /></div><div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"><section className="rounded-lg border border-slate-800/80 bg-[#0D121F] p-5"><div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-widest text-cyan-400">Exposure map</p><h2 className="mt-1 text-lg font-semibold text-white">Symbol net exposure</h2></div><span className="text-[10px] text-slate-600">Auto-refresh 10s</span></div><div className="space-y-4">{exposure.map((row) => <div key={row.symbol}><div className="mb-1 flex justify-between text-xs"><strong className="text-slate-200">{row.symbol}</strong><span className={Number(row.net_volume) >= 0 ? "text-emerald-300" : "text-rose-300"}>{Number(row.net_volume).toFixed(2)} net</span></div><div className="flex h-2 gap-1 overflow-hidden rounded bg-slate-800"><div className="rounded bg-emerald-400" style={{ width: `${Number(row.total_buy_lots) / maxExposure * 50}%` }} /><div className="rounded bg-rose-400" style={{ width: `${Number(row.total_sell_lots) / maxExposure * 50}%` }} /></div><div className="mt-1 flex justify-between text-[10px] text-slate-600"><span>Long {Number(row.total_buy_lots).toFixed(2)}</span><span>Short {Number(row.total_sell_lots).toFixed(2)}</span></div></div>)}{exposure.length === 0 && <p className="py-8 text-center text-sm text-slate-600">No open exposure.</p>}</div></section><section className="rounded-lg border border-slate-800/80 bg-[#0D121F] p-5"><div className="mb-5 flex items-center gap-2"><SlidersHorizontal size={16} className="text-cyan-300" /><h2 className="text-lg font-semibold text-white">Risk limits</h2></div><form className="space-y-4" onSubmit={saveRules}><NumberField label="Max leverage" value={rules.max_leverage} onChange={(value) => setRules({ ...rules, max_leverage: Number(value) })} /><NumberField label="Margin call level %" value={rules.margin_call_level} onChange={(value) => setRules({ ...rules, margin_call_level: value })} /><NumberField label="Stop-out level %" value={rules.stop_out_level} onChange={(value) => setRules({ ...rules, stop_out_level: value })} /><NumberField label="Max lot size" value={rules.max_lot_size} onChange={(value) => setRules({ ...rules, max_lot_size: value })} /><NumberField label="Max drawdown alert %" value={rules.max_drawdown_alert} onChange={(value) => setRules({ ...rules, max_drawdown_alert: value })} /><label className="block text-xs text-slate-400">Prohibited symbols<input value={rules.prohibited_symbols_json.join(", ")} onChange={(event) => setRules({ ...rules, prohibited_symbols_json: event.target.value.toUpperCase().split(",").map((value) => value.trim()).filter(Boolean) })} placeholder="XAUUSD, BTCUSD" className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-xs text-slate-200 outline-none focus:border-cyan-400/60" /></label><button disabled={savingRules} className="w-full rounded-md bg-cyan-400 px-4 py-2.5 text-xs font-bold text-slate-950 disabled:opacity-50" type="submit">{savingRules ? "Saving..." : "Save risk limits"}</button></form></section></div><section className="mt-5 overflow-hidden rounded-lg border border-slate-800/80 bg-[#0D121F]"><div className="flex flex-col gap-3 border-b border-slate-800 p-5 lg:flex-row lg:items-center"><div><p className="text-[10px] uppercase tracking-widest text-cyan-400">Live positions</p><h2 className="mt-1 text-lg font-semibold text-white">Open trades <span className="ml-2 rounded bg-cyan-400/10 px-2 py-1 text-[10px] text-cyan-300">{visiblePositions.length}</span></h2></div><div className="flex flex-wrap gap-2 lg:ml-auto"><select aria-label="Filter by symbol" value={symbol} onChange={(event) => setSymbol(event.target.value)} className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-xs text-slate-300"><option value="ALL">All symbols</option>{Array.from(new Set(positions.map((position) => position.symbol))).map((item) => <option key={item}>{item}</option>)}</select><input aria-label="Filter by account" value={account} onChange={(event) => setAccount(event.target.value)} placeholder="Account ID" className="w-32 rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-xs text-slate-300 outline-none focus:border-cyan-400/60" /><select aria-label="Filter by side" value={side} onChange={(event) => setSide(event.target.value as Side | "ALL")} className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-xs text-slate-300"><option value="ALL">Both sides</option><option value="BUY">Buy</option><option value="SELL">Sell</option></select></div></div><div className="overflow-x-auto"><table className="w-full min-w-[920px] text-left"><thead className="bg-[#0A0E18] text-[10px] uppercase tracking-wider text-slate-500"><tr>{["Symbol", "Account", "Side", "Volume", "Open / current", "Floating P&L", "Status", "Action"].map((heading) => <th key={heading} className="px-5 py-3 font-medium">{heading}</th>)}</tr></thead><tbody className="divide-y divide-slate-800/70">{visiblePositions.map((position) => <tr key={position.id} className="hover:bg-cyan-500/[.025]"><td className="px-5 py-4 font-semibold text-white">{position.symbol}</td><td className="px-5 py-4 font-mono text-xs text-slate-400">{position.account_id.slice(0, 8)}...</td><td className={`px-5 py-4 text-xs font-bold ${position.side === "BUY" ? "text-emerald-300" : "text-rose-300"}`}>{position.side}</td><td className="px-5 py-4 text-xs text-slate-300">{position.volume}</td><td className="px-5 py-4 text-xs text-slate-400">{position.open_price} <span className="text-slate-600">/</span> {position.current_price}</td><td className={`px-5 py-4 text-xs font-semibold ${Number(position.floating_pnl) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{money.format(Number(position.floating_pnl))}</td><td className="px-5 py-4"><span className="rounded bg-emerald-400/10 px-2 py-1 text-[10px] text-emerald-300">{position.status}</span></td><td className="px-5 py-4"><button type="button" disabled={closingId === position.id} onClick={() => void forceClose(position)} className="inline-flex items-center gap-1 rounded border border-rose-500/30 px-2.5 py-1.5 text-[10px] text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"><X size={13} /> {closingId === position.id ? "Closing" : "Force close"}</button></td></tr>)}</tbody></table>{visiblePositions.length === 0 && <div className="p-12 text-center text-sm text-slate-600">No open positions match the filters.</div>}</div></section>{metrics && metrics.high_risk_accounts.length > 0 && <section className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-5"><h2 className="flex items-center gap-2 text-sm font-semibold text-amber-200"><AlertTriangle size={16} /> High-risk accounts</h2><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{metrics.high_risk_accounts.map((risk) => <div key={risk.account_id} className="rounded border border-amber-500/20 bg-[#0D121F] p-3"><p className="font-mono text-[10px] text-slate-400">{risk.account_id.slice(0, 8)}...</p><strong className="mt-2 block text-sm text-amber-200">{Number(risk.margin_usage_percent).toFixed(2)}% usage</strong><small className="text-[10px] text-slate-600">Equity {money.format(Number(risk.equity))}</small></div>)}</div></section>}</div></main>;
+}
+
+function Metric({ label, value, detail, tone = "neutral" }: { label: string; value: string; detail: string; tone?: "neutral" | "positive" | "negative" }) { return <article className="rounded-lg border border-slate-800/80 bg-[#0D121F] p-5"><p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p><strong className={`mt-2 block text-2xl ${tone === "positive" ? "text-emerald-300" : tone === "negative" ? "text-rose-300" : "text-white"}`}>{value}</strong><span className="mt-2 block text-[10px] text-slate-600">{detail}</span></article>; }
+function NumberField({ label, value, onChange }: { label: string; value: number | string; onChange: (value: string) => void }) { return <label className="block text-xs text-slate-400">{label}<input type="number" min="0" step="0.01" value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-xs text-slate-200 outline-none focus:border-cyan-400/60" /></label>; }
