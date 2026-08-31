"use client";

import { useState, useEffect } from "react";
import { Plus, Search, Edit2, Trash2, TrendingUp, Users, Award, Percent } from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

interface IBPartner {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  company_name?: string;
  ib_level: number;
  total_referrals?: number;
  commission_earned?: string;
  created_at: string;
}

interface IBPage {
  items: IBPartner[];
  total: number;
}

export default function IBPartnerPage() {
  const [partners, setPartners] = useState<IBPartner[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingPartner, setEditingPartner] = useState<IBPartner | null>(null);
  const [message, setMessage] = useState("");

  const limit = 20;

  useEffect(() => {
    loadPartners();
  }, [offset, search]);

  async function loadPartners() {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
        ...(search && { search }),
      });

      const response = await fetch(`/api/v1/broker/ib-partners?${query}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to load");
      const data: IBPage = await response.json();
      setPartners(data.items);
      setTotal(data.total);
    } catch (e) {
      setMessage((e instanceof Error ? e.message : "Error loading") + " ❌");
    } finally {
      setLoading(false);
    }
  }

  async function deletePartner(id: string) {
    if (!confirm("Delete this IB partner?")) return;
    try {
      const response = await fetch(`/api/v1/broker/ib-partners/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("Failed to delete");
      setPartners(partners.filter((p) => p.id !== id));
      setMessage("Partner deleted.");
    } catch {
      setMessage("Failed to delete ❌");
    }
  }

  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl">
        <header className="mb-7">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">CRM Operations</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">IB Partner Management</h1>
          <p className="mt-2 text-sm text-slate-500">Manage affiliate partners and track commissions and referrals.</p>
        </header>

        {message && (
          <div className="mb-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search partners..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
              className="w-full rounded border border-slate-700 bg-[#070A11] pl-10 pr-3 py-2 text-sm text-slate-200"
            />
          </div>

          <button
            onClick={() => {
              setEditingPartner(null);
              setShowModal(true);
            }}
            className="rounded-md bg-cyan-400 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-cyan-500"
          >
            <Plus size={14} className="mr-1 inline" /> New Partner
          </button>
        </div>

        <div className="overflow-hidden rounded-lg border border-slate-800 bg-[#0D121F]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Partner</th>
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">Level</th>
                <th className="px-6 py-3 font-medium text-right">Referrals</th>
                <th className="px-6 py-3 font-medium text-right">Commission</th>
                <th className="px-6 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    Loading...
                  </td>
                </tr>
              ) : partners.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    No partners found.
                  </td>
                </tr>
              ) : (
                partners.map((partner) => (
                  <tr key={partner.id} className="hover:bg-slate-800/30">
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">
                        {partner.first_name} {partner.last_name}
                      </div>
                      <div className="text-[10px] text-slate-500">{partner.company_name}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-300 text-[10px] font-mono">{partner.email}</td>
                    <td className="px-6 py-4">
                      <span className="rounded bg-purple-400/10 px-2 py-1 text-[10px] text-purple-300">
                        Level {partner.ib_level}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-mono">{partner.total_referrals || 0}</td>
                    <td className="px-6 py-4 text-right font-mono text-emerald-300">
                      {partner.commission_earned || "$0.00"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => {
                          setEditingPartner(partner);
                          setShowModal(true);
                        }}
                        className="mr-2 text-slate-400 hover:text-cyan-300"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => deletePartner(partner.id)} className="text-slate-400 hover:text-rose-300">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {!loading && total > 0 && (
            <div className="flex items-center justify-between border-t border-slate-800 px-6 py-3 text-[10px] text-slate-500">
              <div>
                Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
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

        {/* Stats */}
        <div className="mt-6 grid gap-3 sm:grid-cols-4">
          <StatCard icon={Users} label="Total Partners" value={String(total)} />
          <StatCard icon={Award} label="Active Tier 1" value="14" />
          <StatCard icon={Percent} label="Avg Commission" value="18.5%" />
          <StatCard icon={TrendingUp} label="This Month" value="$48.5K" />
        </div>

        {showModal && (
          <IBFormModal
            partner={editingPartner}
            onClose={() => setShowModal(false)}
            onSave={() => {
              setShowModal(false);
              loadPartners();
            }}
          />
        )}
      </main>
    </MainLayout>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
          <strong className="mt-2 block text-2xl text-white">{value}</strong>
        </div>
        <Icon size={24} className="text-cyan-300/30" />
      </div>
    </div>
  );
}

function IBFormModal({
  partner,
  onClose,
  onSave,
}: {
  partner: IBPartner | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [formData, setFormData] = useState({
    first_name: partner?.first_name || "",
    last_name: partner?.last_name || "",
    email: partner?.email || "",
    company_name: partner?.company_name || "",
    ib_level: partner?.ib_level || 1,
  });
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      const url = partner ? `/api/v1/broker/ib-partners/${partner.id}` : "/api/v1/broker/ib-partners";
      const method = partner ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) throw new Error("Failed to save");
      onSave();
    } catch (e) {
      alert((e instanceof Error ? e.message : "Error saving") + " ❌");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-lg border border-slate-700 bg-[#0D121F] p-6">
        <h2 className="text-lg font-semibold text-white">{partner ? "Edit Partner" : "New IB Partner"}</h2>

        <div className="mt-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="First name"
              value={formData.first_name}
              onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
              className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            />
            <input
              type="text"
              placeholder="Last name"
              value={formData.last_name}
              onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
              className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            />
          </div>

          <input
            type="email"
            placeholder="Email"
            required
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />

          <input
            type="text"
            placeholder="Company Name"
            value={formData.company_name}
            onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />

          <label className="block">
            <span className="text-xs text-slate-400">IB Level</span>
            <select
              value={formData.ib_level}
              onChange={(e) => setFormData({ ...formData, ib_level: parseInt(e.target.value) })}
              className="mt-1 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            >
              {[1, 2, 3, 4, 5].map((level) => (
                <option key={level} value={level}>
                  Level {level}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="flex-1 rounded-md bg-cyan-400 px-4 py-2 text-xs font-bold text-slate-950 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Partner"}
          </button>
        </div>
      </div>
    </div>
  );
}
