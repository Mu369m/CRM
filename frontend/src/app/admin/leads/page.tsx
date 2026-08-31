"use client";

import { useState, useEffect } from "react";
import { Plus, Search, Filter, Edit2, Trash2, Archive, ChevronRight, TrendingUp, Users } from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  country?: string;
  source?: string;
  stage_id: string;
  stage_name: string;
  lead_score: number;
  created_at: string;
}

interface LeadPage {
  items: Lead[];
  total: number;
}

export default function LeadManagementPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedStage, setSelectedStage] = useState("ALL");
  const [showModal, setShowModal] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [message, setMessage] = useState("");

  const limit = 20;
  const stages = ["New Lead", "Contacted", "Interested", "Qualified", "Proposal", "Negotiation", "Won", "Lost"];

  useEffect(() => {
    loadLeads();
  }, [offset, search, selectedStage]);

  async function loadLeads() {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
        ...(search && { search }),
        ...(selectedStage !== "ALL" && { stage: selectedStage }),
      });

      const response = await fetch(`/api/v1/broker/leads?${query}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to load");
      const data: LeadPage = await response.json();
      setLeads(data.items);
      setTotal(data.total);
    } catch (e) {
      setMessage((e instanceof Error ? e.message : "Error loading leads") + " ❌");
    } finally {
      setLoading(false);
    }
  }

  async function deleteLead(id: string) {
    if (!confirm("Delete this lead?")) return;
    try {
      const response = await fetch(`/api/v1/broker/leads/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("Failed to delete");
      setLeads(leads.filter((l) => l.id !== id));
      setMessage("Lead deleted.");
    } catch {
      setMessage("Failed to delete lead ❌");
    }
  }

  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl">
        <header className="mb-7">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">CRM Operations</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Lead Management</h1>
          <p className="mt-2 text-sm text-slate-500">Track and manage prospective clients through your pipeline.</p>
        </header>

        {message && (
          <div className="mb-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex flex-1 gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search leads..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
                className="w-full rounded border border-slate-700 bg-[#070A11] pl-10 pr-3 py-2 text-sm text-slate-200"
              />
            </div>

            <select
              value={selectedStage}
              onChange={(e) => {
                setSelectedStage(e.target.value);
                setOffset(0);
              }}
              className="rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            >
              <option value="ALL">All Stages</option>
              {stages.map((stage) => (
                <option key={stage} value={stage}>
                  {stage}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => {
              setEditingLead(null);
              setShowModal(true);
            }}
            className="rounded-md bg-cyan-400 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-cyan-500"
          >
            <Plus size={14} className="mr-1 inline" /> New Lead
          </button>
        </div>

        <div className="overflow-hidden rounded-lg border border-slate-800 bg-[#0D121F]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">Stage</th>
                <th className="px-6 py-3 font-medium">Score</th>
                <th className="px-6 py-3 font-medium">Source</th>
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
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    No leads found.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-slate-800/30">
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">
                        {lead.first_name} {lead.last_name}
                      </div>
                      <div className="text-[10px] text-slate-500">{lead.country}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-300">{lead.email}</td>
                    <td className="px-6 py-4">
                      <span className="rounded bg-cyan-400/10 px-2 py-1 text-[10px] text-cyan-300">
                        {lead.stage_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-300">{lead.lead_score}</td>
                    <td className="px-6 py-4 text-slate-500 text-[10px]">{lead.source}</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => {
                          setEditingLead(lead);
                          setShowModal(true);
                        }}
                        className="mr-2 text-slate-400 hover:text-cyan-300"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => deleteLead(lead.id)} className="text-slate-400 hover:text-rose-300">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Pagination */}
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
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Total Leads</p>
            <strong className="mt-2 block text-2xl text-white">{total}</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Conversion Rate</p>
            <strong className="mt-2 block text-2xl text-emerald-300">12.4%</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Avg Lead Score</p>
            <strong className="mt-2 block text-2xl text-cyan-300">42</strong>
          </div>
        </div>

        {/* Modal will be handled by another component */}
        {showModal && (
          <LeadFormModal
            lead={editingLead}
            onClose={() => setShowModal(false)}
            onSave={() => {
              setShowModal(false);
              loadLeads();
            }}
          />
        )}
      </main>
    </MainLayout>
  );
}

function LeadFormModal({
  lead,
  onClose,
  onSave,
}: {
  lead: Lead | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [formData, setFormData] = useState({
    first_name: lead?.first_name || "",
    last_name: lead?.last_name || "",
    email: lead?.email || "",
    phone: lead?.phone || "",
    country: lead?.country || "",
    source: lead?.source || "",
  });
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      const url = lead ? `/api/v1/broker/leads/${lead.id}` : "/api/v1/broker/leads";
      const method = lead ? "PUT" : "POST";

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
        <h2 className="text-lg font-semibold text-white">{lead ? "Edit Lead" : "New Lead"}</h2>

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
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />

          <input
            type="tel"
            placeholder="Phone"
            value={formData.phone}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />

          <input
            type="text"
            placeholder="Country"
            value={formData.country}
            onChange={(e) => setFormData({ ...formData, country: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          />

          <select
            value={formData.source}
            onChange={(e) => setFormData({ ...formData, source: e.target.value })}
            className="w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
          >
            <option value="">Select source...</option>
            <option value="Google">Google</option>
            <option value="Facebook">Facebook</option>
            <option value="Referral">Referral</option>
            <option value="Website">Website</option>
          </select>
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
            {saving ? "Saving..." : "Save Lead"}
          </button>
        </div>
      </div>
    </div>
  );
}
