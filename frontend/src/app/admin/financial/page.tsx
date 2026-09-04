"use client";

import { useState, useEffect } from "react";
import {
  Search,
  Check,
  X,
  Clock,
  TrendingUp,
  ArrowDownRight,
  ArrowUpRight,
} from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

interface Transaction {
  id: string;
  client_id: string;
  client_name: string;
  type: "DEPOSIT" | "WITHDRAWAL";
  amount: string;
  currency: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED";
  method: string;
  created_at: string;
}

interface TransactionPage {
  items: Transaction[];
  total: number;
}

export default function FinancialOperationsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [message, setMessage] = useState("");

  const limit = 20;

  useEffect(() => {
    loadTransactions();
  }, [offset, typeFilter, statusFilter]);

  async function loadTransactions() {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
        ...(typeFilter !== "ALL" && { type: typeFilter }),
        ...(statusFilter !== "ALL" && { status: statusFilter }),
      });

      const response = await fetch(`/api/v1/broker/transactions?${query}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      if (!response.ok) throw new Error("Failed to load");
      const data: TransactionPage = await response.json();
      setTransactions(data.items);
      setTotal(data.total);
    } catch (e) {
      setMessage((e instanceof Error ? e.message : "Error loading") + " ❌");
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(id: string, newStatus: "APPROVED" | "REJECTED") {
    try {
      const response = await fetch(`/api/v1/broker/transactions/${id}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) throw new Error("Failed to update");
      setMessage(`Transaction ${newStatus.toLowerCase()}.`);
      loadTransactions();
    } catch {
      setMessage("Failed to update ❌");
    }
  }

  const money = (val: string) =>
    `$${parseFloat(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const statusColor = (status: string) => {
    switch (status) {
      case "PENDING":
        return "bg-amber-400/10 text-amber-300";
      case "APPROVED":
        return "bg-emerald-400/10 text-emerald-300";
      case "COMPLETED":
        return "bg-cyan-400/10 text-cyan-300";
      case "REJECTED":
        return "bg-rose-400/10 text-rose-300";
      default:
        return "bg-slate-400/10 text-slate-300";
    }
  };

  return (
    <MainLayout panel="broker">
      <main className="mx-auto max-w-6xl">
        <header className="mb-7">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">
            Financial Operations
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            Deposits & Withdrawals
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Review and approve client financial transactions.
          </p>
        </header>

        {message && (
          <div className="mb-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setOffset(0);
            }}
            className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          >
            <option value="ALL">All Types</option>
            <option value="DEPOSIT">Deposits</option>
            <option value="WITHDRAWAL">Withdrawals</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setOffset(0);
            }}
            className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          >
            <option value="ALL">All Status</option>
            <option value="PENDING">Pending Review</option>
            <option value="APPROVED">Approved</option>
            <option value="COMPLETED">Completed</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        <div className="overflow-hidden rounded-lg border border-slate-800 bg-[#0D121F]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Client</th>
                <th className="px-6 py-3 font-medium">Type</th>
                <th className="px-6 py-3 font-medium text-right">Amount</th>
                <th className="px-6 py-3 font-medium">Method</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Date</th>
                <th className="px-6 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {loading ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-slate-500"
                  >
                    Loading...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-slate-500"
                  >
                    No transactions found.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-800/30">
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">
                        {tx.client_name}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500">
                        {tx.client_id.slice(0, 8)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {tx.type === "DEPOSIT" ? (
                        <ArrowDownRight
                          size={16}
                          className="text-emerald-300"
                        />
                      ) : (
                        <ArrowUpRight size={16} className="text-rose-300" />
                      )}
                    </td>
                    <td className="px-6 py-4 text-right font-mono font-semibold">
                      {money(tx.amount)}
                    </td>
                    <td className="px-6 py-4 text-[10px] text-slate-400">
                      {tx.method}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`rounded px-2 py-1 text-[10px] font-medium ${statusColor(tx.status)}`}
                      >
                        {tx.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-[10px] text-slate-500">
                      {new Date(tx.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {tx.status === "PENDING" ? (
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => updateStatus(tx.id, "APPROVED")}
                            className="rounded border border-emerald-500/30 px-2 py-1 text-[10px] text-emerald-300 hover:bg-emerald-500/10"
                          >
                            <Check size={12} className="inline mr-1" /> Approve
                          </button>
                          <button
                            onClick={() => updateStatus(tx.id, "REJECTED")}
                            className="rounded border border-rose-500/30 px-2 py-1 text-[10px] text-rose-300 hover:bg-rose-500/10"
                          >
                            <X size={12} className="inline mr-1" /> Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-[10px] text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {!loading && total > 0 && (
            <div className="flex items-center justify-between border-t border-slate-800 px-6 py-3 text-[10px] text-slate-500">
              <div>
                Showing {offset + 1}-{Math.min(offset + limit, total)} of{" "}
                {total}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="rounded px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total}
                  className="rounded px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Summary Stats */}
        <div className="mt-6 grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Pending Review
            </p>
            <strong className="mt-2 block text-2xl text-amber-300">12</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Total Deposits (24h)
            </p>
            <strong className="mt-2 block text-2xl text-emerald-300">
              $1.24M
            </strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Total Withdrawals (24h)
            </p>
            <strong className="mt-2 block text-2xl text-rose-300">$340K</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Net Flow
            </p>
            <strong className="mt-2 block text-2xl text-cyan-300">
              +$900K
            </strong>
          </div>
        </div>
      </main>
    </MainLayout>
  );
}
