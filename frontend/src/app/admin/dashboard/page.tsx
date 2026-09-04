"use client";

import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
  Download,
  Eye,
  Plus,
  TrendingUp,
  Users,
} from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

type WidgetKey = "clients" | "cashflow" | "kyc" | "top-traders";

type StatCardProps = {
  label: string;
  value: string;
  change: string;
  icon: typeof Users;
};

export default function DashboardPage() {
  const [widgets, setWidgets] = useState<WidgetKey[]>([
    "clients",
    "cashflow",
    "kyc",
    "top-traders",
  ]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 200);
    return () => window.clearTimeout(timer);
  }, []);

  const toggleWidget = (key: WidgetKey) => {
    setWidgets((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    );
  };

  if (loading) {
    return (
      <MainLayout>
        <main className="mx-auto max-w-7xl py-10">
          <p className="text-[var(--text-secondary)]">Loading dashboard...</p>
        </main>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <main className="mx-auto max-w-7xl py-6">
        <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[.25em] text-[var(--color-brand)]">
              Broker insights
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">
              Dashboard
            </h1>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              Performance overview across deposits, trading activity, and
              compliance.
            </p>
          </div>

          <div className="flex gap-2">
            <button className="rounded border border-[var(--border-secondary)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
              <Download size={14} className="mr-1 inline" /> Export
            </button>
            <button className="rounded-md bg-[var(--color-brand)] px-3 py-2 text-xs font-bold text-white hover:bg-[var(--color-brand-hover)]">
              <Plus size={14} className="mr-1 inline" /> Add widget
            </button>
          </div>
        </header>

        <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total clients"
            value="4,823"
            change="+12.4%"
            icon={Users}
          />
          <StatCard
            label="Active traders"
            value="3,148"
            change="+8.1%"
            icon={TrendingUp}
          />
          <StatCard
            label="Net deposits"
            value="$4.2M"
            change="+24.6%"
            icon={DollarSign}
          />
          <StatCard
            label="Pending KYC"
            value="24"
            change="Action needed"
            icon={Eye}
          />
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.7fr)]">
          {widgets.includes("cashflow") && (
            <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
                    Cashflow
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                    Deposits vs withdrawals
                  </h2>
                </div>
                <button
                  onClick={() => toggleWidget("cashflow")}
                  className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                  aria-label="Hide cashflow widget"
                >
                  ✕
                </button>
              </div>

              <div className="mb-4 flex gap-5 text-[11px] text-[var(--text-secondary)]">
                <span>
                  <span className="mr-2 inline-block size-2 rounded-full bg-[var(--color-success)]" />{" "}
                  Deposits
                </span>
                <span>
                  <span className="mr-2 inline-block size-2 rounded-full bg-[var(--color-error)]" />{" "}
                  Withdrawals
                </span>
              </div>

              <div className="grid h-48 grid-cols-7 gap-2">
                {[42, 58, 36, 70, 60, 96, 80].map((height, index) => (
                  <div key={index} className="flex h-full items-end gap-2">
                    <div
                      className="w-1/2 rounded-t bg-[var(--color-success)] opacity-80"
                      style={{ height: `${height}%` }}
                    />
                    <div
                      className="w-1/2 rounded-t bg-[var(--color-error)] opacity-70"
                      style={{ height: `${Math.max(18, height - 18)}%` }}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-6">
            {widgets.includes("clients") && (
              <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
                      Accounts
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                      Client mix
                    </h2>
                  </div>
                  <button
                    onClick={() => toggleWidget("clients")}
                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                    aria-label="Hide clients widget"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between text-sm text-[var(--text-secondary)]">
                    <span>Live</span>
                    <span className="font-semibold text-[var(--color-success-text)]">
                      68%
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-tertiary)]">
                    <div className="h-full w-[68%] rounded-full bg-[var(--color-success)]" />
                  </div>
                  <div className="flex items-center justify-between text-sm text-[var(--text-secondary)]">
                    <span>Demo</span>
                    <span className="font-semibold text-[var(--color-brand)]">
                      32%
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-tertiary)]">
                    <div className="h-full w-[32%] rounded-full bg-[var(--color-brand)]" />
                  </div>
                </div>
              </div>
            )}

            {widgets.includes("kyc") && (
              <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
                      Compliance
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                      KYC status
                    </h2>
                  </div>
                  <button
                    onClick={() => toggleWidget("kyc")}
                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                    aria-label="Hide kyc widget"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3 text-sm text-[var(--text-secondary)]">
                  <div className="flex items-center justify-between">
                    <span>Verified</span>
                    <span className="text-[var(--color-success-text)]">
                      91%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Pending</span>
                    <span className="text-[var(--color-warning-text)]">24</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Rejected</span>
                    <span className="text-[var(--color-error-text)]">7</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
          <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
                  Operations
                </p>
                <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                  Approval queue
                </h2>
              </div>
              <span className="rounded bg-amber-500/10 px-2 py-1 text-[10px] text-amber-300">
                8 open
              </span>
            </div>

            <div className="space-y-3">
              {[
                {
                  client: "Amelia Thompson",
                  type: "Deposit",
                  amount: "$18,500",
                  status: "Review",
                  color: "text-[var(--color-warning-text)]",
                },
                {
                  client: "Nikolai Petrov",
                  type: "Withdrawal",
                  amount: "$7,240",
                  status: "Pending",
                  color: "text-[var(--color-brand)]",
                },
                {
                  client: "Sofia Mendes",
                  type: "Deposit",
                  amount: "$42,000",
                  status: "Approved",
                  color: "text-[var(--color-success-text)]",
                },
              ].map((item) => (
                <div
                  key={item.client}
                  className="flex items-center justify-between rounded border border-[var(--border-primary)] p-3"
                >
                  <div>
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      {item.client}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--text-tertiary)]">
                      {item.type === "Deposit" ? (
                        <ArrowDownRight
                          size={12}
                          className="text-[var(--color-success-text)]"
                        />
                      ) : (
                        <ArrowUpRight
                          size={12}
                          className="text-[var(--color-error-text)]"
                        />
                      )}
                      {item.type}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm text-[var(--text-secondary)]">
                      {item.amount}
                    </div>
                    <div className={`mt-1 text-[10px] ${item.color}`}>
                      {item.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {widgets.includes("top-traders") && (
            <div className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
                    Leaders
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                    Top traders
                  </h2>
                </div>
                <button
                  onClick={() => toggleWidget("top-traders")}
                  className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                  aria-label="Hide top traders widget"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4 text-sm">
                {[
                  { name: "Amelia T.", equity: "$1.28M" },
                  { name: "Nikolai P.", equity: "$980K" },
                  { name: "Sofia M.", equity: "$860K" },
                ].map((trader, idx) => (
                  <div
                    key={trader.name}
                    className="flex items-center justify-between rounded border border-[var(--border-primary)] px-3 py-2"
                  >
                    <div className="flex items-center gap-3">
                      <span className="grid size-8 place-items-center rounded-full bg-[var(--color-brand-light)] text-[var(--color-brand)] text-[10px] font-bold">
                        {idx + 1}
                      </span>
                      <span className="text-[var(--text-secondary)]">
                        {trader.name}
                      </span>
                    </div>
                    <span className="font-mono text-[var(--color-success-text)]">
                      {trader.equity}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </MainLayout>
  );
}

function StatCard({ label, value, change, icon: Icon }: StatCardProps) {
  return (
    <article className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="rounded-md bg-[var(--color-brand-light)] p-2 text-[var(--color-brand)]">
          <Icon size={18} />
        </div>
        <span className="rounded bg-[var(--color-success-bg)] px-2 py-1 text-[10px] text-[var(--color-success-text)]">
          {change}
        </span>
      </div>
      <p className="text-[10px] uppercase tracking-[.2em] text-[var(--text-tertiary)]">
        {label}
      </p>
      <strong className="mt-2 block text-2xl font-semibold text-[var(--text-primary)]">
        {value}
      </strong>
    </article>
  );
}
