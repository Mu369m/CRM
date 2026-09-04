"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import {
  BarChart3,
  Bell,
  ChevronDown,
  Database,
  FileCheck2,
  Home,
  Handshake,
  Menu,
  Settings2,
  SlidersHorizontal,
  Users,
  UserPlus,
  UserRound,
  WalletCards,
  Workflow,
  X,
} from "lucide-react";
import { ThemeToggle } from "../ui/ThemeToggle";

const traderPrimaryNav = [
  { label: "Overview", href: "/", icon: Home },
  { label: "Trading", href: "/trader-cabinet", icon: BarChart3 },
  { label: "Wallet", href: "/trader-cabinet#wallet", icon: WalletCards },
  { label: "Approvals", href: "/trader-cabinet#approvals", icon: Bell },
];

const traderSecondaryNav = [
  { label: "Profile", href: "/trader/profile", icon: UserRound },
  { label: "IB Partner", href: "/trader/ib", icon: BarChart3 },
];

const brokerPrimaryNav = [
  { label: "Dashboard", href: "/admin/dashboard", icon: Home },
  { label: "Leads", href: "/admin/leads", icon: UserPlus },
  { label: "Clients", href: "/admin/clients", icon: Users },
  { label: "Finance", href: "/admin/finance", icon: WalletCards },
  { label: "KYC & Compliance", href: "/admin/kyc-documents", icon: FileCheck2 },
  { label: "IB Partners", href: "/admin/ib-partners", icon: Handshake },
  { label: "Workflows", href: "/admin/workflows", icon: Workflow },
  { label: "Risk & Trading", href: "/admin/risk", icon: SlidersHorizontal },
];

const brokerSecondaryNav = [
  { label: "Infrastructure", href: "/admin/infrastructure", icon: Database },
  { label: "Broker Settings", href: "/admin/broker-settings", icon: Settings2 },
];

type Panel = "trader" | "broker";

export default function MainLayout({
  children,
  panel = "trader",
}: {
  children: ReactNode;
  panel?: Panel;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const primaryNav = panel === "broker" ? brokerPrimaryNav : traderPrimaryNav;
  const secondaryNav =
    panel === "broker" ? brokerSecondaryNav : traderSecondaryNav;
  const title = panel === "broker" ? "Broker Admin" : "Trader Room";
  const workspace =
    panel === "broker" ? "Broker Operations" : "Northstar Markets";

  return (
    <div className="flex min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* DESKTOP SIDEBAR */}
      <aside className="hidden w-64 flex-shrink-0 border-r border-[var(--border-primary)] bg-[var(--bg-secondary)] lg:flex lg:flex-col">
        <div className="flex flex-col h-full">
          {/* SIDEBAR HEADER */}
          <div className="flex-shrink-0 px-6 py-8">
            <Link href="/" className="flex items-center gap-3 no-underline">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600">
                <span className="text-lg font-bold text-white">N</span>
              </div>
              <div>
                <div className="text-sm font-bold text-[var(--text-primary)]">
                  Northstar
                </div>
                <div className="text-xs text-[var(--text-tertiary)]">
                  {title}
                </div>
              </div>
            </Link>
          </div>

          {/* WORKSPACE SELECTOR */}
          <div className="mx-6 mb-8 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
              Workspace
            </p>
            <button className="mt-3 flex w-full items-center justify-between text-sm font-semibold text-[var(--text-primary)] hover:text-[var(--color-brand)]">
              <span className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                {workspace}
              </span>
              <ChevronDown size={14} className="text-[var(--text-tertiary)]" />
            </button>
          </div>

          {/* PRIMARY NAVIGATION */}
          <nav className="flex-1 space-y-1 px-4 pb-8">
            <p className="mb-4 px-3 text-xs font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
              Navigate
            </p>
            {primaryNav.map((item) => (
              <NavItem key={item.label} {...item} />
            ))}
          </nav>

          {/* SECONDARY NAVIGATION */}
          <nav className="space-y-1 border-t border-[var(--border-primary)] px-4 py-8">
            <p className="mb-4 px-3 text-xs font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
              Account
            </p>
            {secondaryNav.map((item) => (
              <NavItem key={item.label} {...item} />
            ))}
          </nav>

          {/* SIDEBAR FOOTER */}
          <div className="flex-shrink-0 border-t border-[var(--border-primary)] px-4 py-6">
            <div className="rounded-lg bg-[var(--bg-tertiary)] p-4">
              <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
                Status
              </p>
              <p className="mt-2 text-lg font-bold text-emerald-600">99.99%</p>
              <p className="text-xs text-[var(--text-tertiary)]">
                Uptime · Live
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* TOPBAR */}
        <header className="flex h-20 items-center justify-between border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] px-6 lg:px-8 backdrop-blur-sm">
          {/* MOBILE MENU BUTTON */}
          <button
            className="lg:hidden inline-flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>

          {/* MOBILE BRAND */}
          <div className="lg:hidden">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600">
                <span className="text-sm font-bold text-white">N</span>
              </div>
            </Link>
          </div>

          {/* DESKTOP TITLE */}
          <div className="hidden lg:block">
            <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
              {panel === "broker" ? "Broker operations" : "Trader workspace"}
            </p>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {title}
            </h1>
          </div>

          {/* TOPBAR ACTIONS */}
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <button
              className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
              aria-label="Search"
            >
              <span className="text-lg">⌕</span>
            </button>
            <button
              className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-tertiary)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
              aria-label="Notifications"
            >
              <Bell size={20} />
            </button>
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-600 text-white font-bold text-xs">
              RK
            </div>
          </div>
        </header>

        {/* PAGE CONTENT */}
        <main className="flex-1 overflow-auto">
          <div className="p-6 sm:p-8 lg:p-10">{children}</div>
        </main>
      </div>

      {/* MOBILE SIDEBAR DRAWER */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        >
          <aside className="fixed inset-y-0 left-0 z-50 w-64 border-r border-[var(--border-primary)] bg-[var(--bg-secondary)] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-6">
              <Link href="/" className="flex items-center gap-2">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600">
                  <span className="text-lg font-bold text-white">N</span>
                </div>
                <span className="font-bold text-[var(--text-primary)]">
                  Northstar
                </span>
              </Link>
              <button
                className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                onClick={() => setSidebarOpen(false)}
              >
                <X size={24} />
              </button>
            </div>

            <nav className="space-y-1 px-4 py-6">
              {[...primaryNav, ...secondaryNav].map((item) => (
                <NavItem
                  key={item.label}
                  {...item}
                  onClick={() => setSidebarOpen(false)}
                />
              ))}
            </nav>
          </aside>
        </div>
      )}
    </div>
  );
}

function NavItem({
  label,
  href,
  icon: Icon,
  onClick,
}: {
  label: string;
  href: string;
  icon: typeof Home;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex items-center gap-3 rounded-lg border border-transparent px-3 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-all no-underline hover:border-[var(--border-primary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
    >
      <Icon size={18} className="flex-shrink-0" />
      <span>{label}</span>
    </Link>
  );
}
