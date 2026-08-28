"use client";

import { useEffect, useState } from "react";
import { Check, Eye, RefreshCw, Search, X } from "lucide-react";

type TransactionType = "DEPOSIT" | "WITHDRAWAL" | "INTERNAL_TRANSFER";
type TransactionStatus = "PENDING" | "APPROVED" | "REJECTED";
interface Transaction {
  id: string;
  trader_id: string;
  type: TransactionType;
  amount: string;
  currency: string;
  status: TransactionStatus;
  gateway_id: string | null;
  payment_proof_url: string | null;
  rejection_note: string | null;
  created_at: string;
}
interface TransactionPage { items: Transaction[]; total: number; offset: number; limit: number }

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function FinancePage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [statusFilter, setStatusFilter] = useState<TransactionStatus | "ALL">("PENDING");
  const [typeFilter, setTypeFilter] = useState<TransactionType | "ALL">("ALL");
  const [proof, setProof] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<Transaction | null>(null);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("Loading approval queue...");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function loadQueue() {
    setMessage("Loading approval queue...");
    const params = new URLSearchParams({ limit: "50" });
    if (statusFilter !== "ALL") params.set("status", statusFilter);
    if (typeFilter !== "ALL") params.set("type", typeFilter);
    try {
      const response = await fetch(`${api}/api/v1/broker/finance/transactions?${params}`, { headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` } });
      if (!response.ok) throw new Error("Unable to load transactions.");
      const data = await response.json() as TransactionPage;
      setTransactions(data.items);
      setMessage(`${data.total} transaction${data.total === 1 ? "" : "s"} found`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load transactions."); }
  }

  useEffect(() => { void loadQueue(); }, [statusFilter, typeFilter]);

  async function approve(transaction: Transaction) {
    setBusyId(transaction.id);
    try {
      const response = await fetch(`${api}/api/v1/broker/finance/transactions/${transaction.id}/approve`, { method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` } });
      const data = await response.json().catch(() => ({})) as { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Approval failed.");
      setMessage("Transaction approved and wallet settled.");
      await loadQueue();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Approval failed."); } finally { setBusyId(null); }
  }

  async function reject() {
    if (!rejecting || note.trim().length < 3) return;
    setBusyId(rejecting.id);
    try {
      const response = await fetch(`${api}/api/v1/broker/finance/transactions/${rejecting.id}/reject`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` }, body: JSON.stringify({ note: note.trim() }) });
      const data = await response.json().catch(() => ({})) as { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Rejection failed.");
      setRejecting(null); setNote(""); setMessage("Transaction rejected."); await loadQueue();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Rejection failed."); } finally { setBusyId(null); }
  }

  return <main className="min-h-screen bg-[#070A11] px-4 py-7 text-slate-100 sm:px-6 lg:px-8"><div className="mx-auto max-w-7xl"><header className="mb-7 flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-end"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-400">Broker administration / finance</p><h1 className="mt-2 text-3xl font-semibold text-white">Transaction approvals</h1><p className="mt-2 text-sm text-slate-500">Review payment evidence and settle trader wallets with an auditable decision.</p></div><button type="button" onClick={() => void loadQueue()} className="inline-flex items-center gap-2 self-start rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-cyan-400/50 sm:self-auto"><RefreshCw size={14} /> Refresh</button></header><div className="mb-4 flex flex-wrap items-center gap-2"><div className="relative"><Search size={14} className="pointer-events-none absolute left-3 top-2.5 text-slate-600" /><select aria-label="Transaction status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as TransactionStatus | "ALL")} className="rounded-md border border-slate-800 bg-[#0D121F] py-2 pl-8 pr-3 text-xs text-slate-300"><option value="ALL">All statuses</option><option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option></select></div><select aria-label="Transaction type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as TransactionType | "ALL")} className="rounded-md border border-slate-800 bg-[#0D121F] px-3 py-2 text-xs text-slate-300"><option value="ALL">All types</option><option value="DEPOSIT">Deposits</option><option value="WITHDRAWAL">Withdrawals</option><option value="INTERNAL_TRANSFER">Transfers</option></select><span className="ml-auto text-xs text-slate-500">{message}</span></div><section className="overflow-x-auto rounded-lg border border-slate-800/80 bg-[#0D121F]"><table className="w-full min-w-[900px] text-left"><thead className="border-b border-slate-800 bg-[#0A0E18] text-[10px] uppercase tracking-wider text-slate-500"><tr>{["Trader", "Type", "Amount", "Proof", "Submitted", "Status", "Actions"].map((heading) => <th key={heading} className="px-5 py-3 font-medium">{heading}</th>)}</tr></thead><tbody className="divide-y divide-slate-800/70">{transactions.map((transaction) => <tr key={transaction.id} className="hover:bg-cyan-500/[.025]"><td className="px-5 py-4"><strong className="block font-mono text-xs text-slate-200">{transaction.trader_id.slice(0, 8)}...</strong><small className="text-[10px] text-slate-600">{transaction.id.slice(0, 8)}</small></td><td className={`px-5 py-4 text-xs ${transaction.type === "DEPOSIT" ? "text-emerald-300" : "text-rose-300"}`}>{transaction.type.replace("_", " ")}</td><td className="px-5 py-4 text-sm font-semibold text-white">{transaction.amount} <span className="text-[10px] text-slate-500">{transaction.currency}</span></td><td className="px-5 py-4">{transaction.payment_proof_url ? <button type="button" onClick={() => setProof(transaction.payment_proof_url)} className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"><Eye size={14} /> View proof</button> : <span className="text-xs text-slate-600">Not provided</span>}</td><td className="px-5 py-4 text-xs text-slate-500">{new Date(transaction.created_at).toLocaleString()}</td><td className="px-5 py-4"><span className={`rounded px-2 py-1 text-[10px] font-semibold ${transaction.status === "PENDING" ? "bg-amber-400/10 text-amber-300" : transaction.status === "APPROVED" ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-400/10 text-rose-300"}`}>{transaction.status}</span></td><td className="px-5 py-4">{transaction.status === "PENDING" && <div className="flex gap-2"><button type="button" disabled={busyId === transaction.id} onClick={() => void approve(transaction)} className="grid size-8 place-items-center rounded border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50" aria-label="Approve transaction"><Check size={15} /></button><button type="button" disabled={busyId === transaction.id} onClick={() => setRejecting(transaction)} className="grid size-8 place-items-center rounded border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50" aria-label="Reject transaction"><X size={15} /></button></div>}</td></tr>)}</tbody></table>{transactions.length === 0 && <div className="p-12 text-center text-sm text-slate-600">No transactions match these filters.</div>}</section></div>{proof && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/85 p-4" onClick={() => setProof(null)}><section className="max-h-[90vh] w-full max-w-2xl rounded-lg border border-slate-700 bg-[#0D121F] p-4" onClick={(event) => event.stopPropagation()}><div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-semibold text-white">Payment proof</h2><button type="button" onClick={() => setProof(null)} aria-label="Close proof viewer" className="text-slate-500 hover:text-white"><X size={18} /></button></div><img src={proof} alt="Payment proof" className="max-h-[72vh] w-full rounded object-contain" /></section></div>}{rejecting && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/85 p-4"><section className="w-full max-w-md rounded-lg border border-slate-700 bg-[#0D121F] p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-white">Reject transaction</h2><button type="button" onClick={() => setRejecting(null)} aria-label="Close rejection dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div><label className="mt-5 block text-xs text-slate-400">Reason<textarea value={note} onChange={(event) => setNote(event.target.value)} minLength={3} required className="mt-2 min-h-24 w-full rounded border border-slate-700 bg-[#070A11] p-3 text-xs text-slate-200 outline-none focus:border-cyan-400/60" placeholder="Explain why this payment is being rejected." /></label><div className="mt-4 flex justify-end gap-2"><button type="button" onClick={() => setRejecting(null)} className="rounded border border-slate-700 px-3 py-2 text-xs text-slate-400">Cancel</button><button type="button" disabled={busyId === rejecting.id || note.trim().length < 3} onClick={() => void reject()} className="rounded bg-rose-400 px-3 py-2 text-xs font-bold text-slate-950 disabled:opacity-50">Reject transaction</button></div></section></div>}</main>;
}