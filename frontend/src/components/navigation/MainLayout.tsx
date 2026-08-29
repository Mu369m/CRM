"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { BarChart3, Bell, ChevronDown, Home, Menu, UserRound, WalletCards, X, Zap } from "lucide-react";
import { ThemeToggle } from "../ui/ThemeToggle";

const primary = [
  { label: "Home", href: "/", icon: Home },
  { label: "Trading", href: "/trader-cabinet", icon: BarChart3 },
  { label: "Wallet", href: "/trader-cabinet#wallet", icon: WalletCards },
  { label: "Approvals", href: "/trader-cabinet#approvals", icon: Bell },
  { label: "Profile", href: "/trader/profile", icon: UserRound },
  { label: "IB Partner", href: "/trader/ib", icon: BarChart3 },
];

export default function MainLayout({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  return <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)] lg:flex">
    <aside className="hidden w-64 shrink-0 border-r border-[var(--line)] bg-[var(--panel)] px-4 py-6 lg:flex lg:flex-col"><Brand /><div className="mt-8 rounded-md border border-[var(--line)] bg-[var(--paper)] p-3"><p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Workspace</p><div className="mt-2 flex items-center gap-2 text-xs font-semibold text-[var(--ink)]"><span className="size-2 rounded-full bg-emerald-400" /> Northstar Markets <ChevronDown size={14} className="ml-auto text-[var(--muted)]" /></div></div><p className="mb-2 mt-8 px-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Workspace</p><nav className="space-y-1">{primary.map((item) => <NavItem {...item} key={item.label} />)}</nav><div className="mt-auto rounded-md border border-[var(--line)] bg-[var(--paper)] p-3"><p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Account health</p><strong className="mt-2 block text-lg text-emerald-500">99.99%</strong><span className="text-[10px] text-[var(--muted)]">Platform uptime · live</span></div></aside>
    <div className="min-w-0 flex-1 pb-20 lg:pb-0"><header className="flex h-16 items-center justify-between border-b border-[var(--line)] bg-[var(--panel)]/90 px-4 backdrop-blur lg:px-8"><button className="grid size-9 place-items-center rounded border border-[var(--line)] text-[var(--ink)] lg:hidden" onClick={() => setDrawerOpen(true)} aria-label="Open navigation"><Menu size={18} /></button><div className="lg:hidden"><Brand compact /></div><div className="hidden text-[10px] uppercase tracking-[.18em] text-[var(--muted)] lg:block">Broker administration workspace</div><div className="flex items-center gap-3"><ThemeToggle /><span className="hidden items-center gap-2 text-xs text-emerald-500 sm:flex"><span className="size-2 rounded-full bg-emerald-400" /> Secure session</span><span className="grid size-8 place-items-center rounded-full bg-cyan-400/15 text-[10px] font-bold text-cyan-600">RK</span></div></header><div className="p-4 sm:p-6 lg:p-8">{children}</div></div>
    <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-[var(--line)] bg-[var(--panel)]/95 px-2 py-2 backdrop-blur lg:hidden">{primary.map((item) => <NavItem {...item} mobile key={item.label} />)}</nav>
    {drawerOpen && <div className="fixed inset-0 z-50 bg-slate-950/70 lg:hidden" onClick={() => setDrawerOpen(false)}><aside className="h-full w-72 border-r border-[var(--line)] bg-[var(--panel)] p-5" onClick={(event) => event.stopPropagation()}><div className="flex items-center justify-between"><Brand /><button className="text-[var(--muted)]" onClick={() => setDrawerOpen(false)} aria-label="Close navigation"><X size={19} /></button></div><nav className="mt-8 space-y-1">{primary.map((item) => <NavItem {...item} key={item.label} />)}</nav><Link className="mt-8 flex items-center gap-2 rounded-md border border-cyan-500/20 bg-cyan-500/10 p-3 text-xs text-cyan-700" href="/owner-control"><Zap size={15} /> System controls</Link></aside></div>}
  </div>;
}

function Brand({ compact = false }: { compact?: boolean }) { return <Link className="flex items-center gap-2 text-sm font-semibold text-[var(--ink)]" href="/"><span className="grid size-8 place-items-center rounded-md bg-cyan-400/15 text-cyan-600">N</span>{!compact && <span>northstar<span className="text-cyan-600">.</span></span>}</Link>; }
function NavItem({ label, href, icon: Icon, mobile = false }: { label: string; href: string; icon: typeof Home; mobile?: boolean }) { return <Link className={mobile ? "flex flex-col items-center gap-1 rounded px-1 py-1.5 text-[9px] text-[var(--muted)]" : "flex items-center gap-3 rounded-md border border-transparent px-3 py-2.5 text-xs text-[var(--muted)] transition hover:border-[var(--line)] hover:bg-[var(--surface)] hover:text-[var(--ink)]"} href={href}><Icon size={mobile ? 17 : 16} />{label}</Link>; }