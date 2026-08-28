"use client";

import { useRouter } from "next/navigation";
import MainLayout from "@/components/navigation/MainLayout";
import BroadcastBanner from "@/components/dashboard/BroadcastBanner";
import { ArrowDownToLine, ArrowUpToLine, BarChart3, WalletCards } from "lucide-react";

export default function TraderDashboardPage() {
  const router = useRouter();
  return <MainLayout><main className="mx-auto max-w-6xl"><BroadcastBanner /><header className="mb-7"><p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">Trader workspace</p><h1 className="mt-2 text-3xl font-semibold text-white">Account overview</h1><p className="mt-2 text-sm text-slate-500">Monitor your portfolio and manage trading funds.</p></header><div className="grid gap-4 sm:grid-cols-3"><Card icon={WalletCards} label="Portfolio equity" value="$18,004.25" /><Card icon={BarChart3} label="Free margin" value="$16,781.10" /><Card icon={BarChart3} label="Open positions" value="4" /></div><section className="mt-5 rounded-lg border border-slate-800 bg-[#0D121F] p-5"><h2 className="text-base font-semibold text-white">Quick actions</h2><div className="mt-4 flex flex-wrap gap-3"><button className="inline-flex items-center gap-2 rounded-md bg-cyan-400 px-4 py-2.5 text-xs font-bold text-slate-950"><ArrowDownToLine size={15} /> Deposit</button><button className="inline-flex items-center gap-2 rounded-md border border-slate-700 px-4 py-2.5 text-xs text-slate-300"><ArrowUpToLine size={15} /> Withdraw</button><button className="text-xs text-cyan-300" onClick={() => router.push("/trader-cabinet")}>Open full cabinet</button></div></section></main></MainLayout>;
}
function Card({ icon: Icon, label, value }: { icon: typeof WalletCards; label: string; value: string }) { return <article className="rounded-lg border border-slate-800 bg-[#0D121F] p-5"><Icon size={18} className="text-cyan-300" /><p className="mt-5 text-[10px] uppercase tracking-wider text-slate-500">{label}</p><strong className="mt-1 block text-2xl text-white">{value}</strong></article>; }
