"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Plus, Edit2, CheckCircle, AlertCircle } from "lucide-react";

interface Workflow {
  id: string;
  name: string;
  description?: string;
  entity_type: string;
  is_active: boolean;
  trigger_type: string;
  created_at: string;
}

interface NewWorkflow {
  name: string;
  description: string;
  entity_type: string;
  trigger_type: string;
}

const ENTITY_TYPES = [
  "lead",
  "client",
  "deposit",
  "withdrawal",
  "ib_partner",
  "task",
];
const TRIGGER_TYPES = [
  "entity_created",
  "status_changed",
  "time_based",
  "manual",
];

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<NewWorkflow>({
    name: "",
    description: "",
    entity_type: "lead",
    trigger_type: "entity_created",
  });

  const authHeaders = (): HeadersInit => {
    const token = window.localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchWorkflows = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/v1/broker/workflows", {
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error("Failed to fetch workflows");
      const data = await response.json();
      setWorkflows(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  };

  // Fetch workflows
  useEffect(() => {
    const timer = window.setTimeout(() => void fetchWorkflows(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (!formData.name.trim()) {
        setError("Workflow name is required");
        return;
      }

      const method = editingId ? "PUT" : "POST";
      const url = editingId
        ? `/api/v1/broker/workflows/${editingId}`
        : "/api/v1/broker/workflows";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(formData),
      });

      if (!response.ok)
        throw new Error(
          `Failed to ${editingId ? "update" : "create"} workflow`,
        );

      setFormData({
        name: "",
        description: "",
        entity_type: "lead",
        trigger_type: "entity_created",
      });
      setEditingId(null);
      setShowForm(false);
      setError("");
      await fetchWorkflows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save workflow");
    }
  };

  const handleEdit = (workflow: Workflow) => {
    setFormData({
      name: workflow.name,
      description: workflow.description || "",
      entity_type: workflow.entity_type,
      trigger_type: workflow.trigger_type,
    });
    setEditingId(workflow.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this workflow?")) return;
    try {
      const response = await fetch(`/api/v1/broker/workflows/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error("Failed to delete workflow");
      setError("");
      await fetchWorkflows();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete workflow",
      );
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData({
      name: "",
      description: "",
      entity_type: "lead",
      trigger_type: "entity_created",
    });
  };

  const handleViewDetails = (workflowId: string) => {
    router.push(`/admin/workflows/${workflowId}`);
  };

  return (
    <div className="min-h-screen bg-[#0D121F] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2">Workflows</h1>
            <p className="text-gray-400">
              Automate business processes and lead management
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="bg-cyan-500 hover:bg-cyan-600 text-black font-semibold py-3 px-6 rounded-lg flex items-center gap-2 transition"
          >
            <Plus size={20} />
            Create Workflow
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-400 p-4 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Create/Edit Form */}
        {showForm && (
          <div className="bg-[#1a2332] border border-gray-700 rounded-lg p-6 mb-8">
            <h2 className="text-xl font-bold mb-4">
              {editingId ? "Edit Workflow" : "Create New Workflow"}
            </h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder="e.g., Auto-assign high-value leads"
                    className="w-full bg-[#0D121F] border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Entity Type *
                  </label>
                  <select
                    value={formData.entity_type}
                    onChange={(e) =>
                      setFormData({ ...formData, entity_type: e.target.value })
                    }
                    className="w-full bg-[#0D121F] border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  >
                    {ENTITY_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Trigger Type *
                  </label>
                  <select
                    value={formData.trigger_type}
                    onChange={(e) =>
                      setFormData({ ...formData, trigger_type: e.target.value })
                    }
                    className="w-full bg-[#0D121F] border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  >
                    {TRIGGER_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type
                          .split("_")
                          .map(
                            (word) =>
                              word.charAt(0).toUpperCase() + word.slice(1),
                          )
                          .join(" ")}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Description
                  </label>
                  <input
                    type="text"
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({ ...formData, description: e.target.value })
                    }
                    placeholder="What does this workflow do?"
                    className="w-full bg-[#0D121F] border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="submit"
                  className="bg-cyan-500 hover:bg-cyan-600 text-black font-semibold py-2 px-6 rounded-lg transition"
                >
                  {editingId ? "Update" : "Create"}
                </button>
                <button
                  type="button"
                  onClick={handleCancel}
                  className="bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 px-6 rounded-lg transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full"></div>
            <p className="text-gray-400 mt-4">Loading workflows...</p>
          </div>
        )}

        {/* Workflows Grid */}
        {!loading && workflows.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workflows.map((workflow) => (
              <div
                key={workflow.id}
                className="bg-[#1a2332] border border-gray-700 rounded-lg p-6 hover:border-cyan-500 transition group cursor-pointer"
                onClick={() => handleViewDetails(workflow.id)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-bold">{workflow.name}</h3>
                    {workflow.description && (
                      <p className="text-gray-400 text-sm mt-1">
                        {workflow.description}
                      </p>
                    )}
                  </div>
                  {workflow.is_active ? (
                    <CheckCircle
                      size={20}
                      className="text-green-500 shrink-0"
                    />
                  ) : (
                    <AlertCircle
                      size={20}
                      className="text-yellow-500 shrink-0"
                    />
                  )}
                </div>

                <div className="flex gap-2 mb-4">
                  <span className="bg-cyan-500/20 text-cyan-300 text-xs font-medium px-3 py-1 rounded-full">
                    {workflow.entity_type}
                  </span>
                  <span className="bg-purple-500/20 text-purple-300 text-xs font-medium px-3 py-1 rounded-full">
                    {workflow.trigger_type}
                  </span>
                </div>

                <div className="text-xs text-gray-500 mb-4">
                  Created {new Date(workflow.created_at).toLocaleDateString()}
                </div>

                <div className="flex gap-2 pt-4 border-t border-gray-700 group-hover:opacity-100 opacity-0 transition">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEdit(workflow);
                    }}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-3 rounded-lg text-sm flex items-center justify-center gap-2 transition"
                  >
                    <Edit2 size={16} />
                    Edit
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(workflow.id);
                    }}
                    className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-3 rounded-lg text-sm flex items-center justify-center gap-2 transition"
                  >
                    <Trash2 size={16} />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && workflows.length === 0 && (
          <div className="bg-[#1a2332] border border-dashed border-gray-600 rounded-lg p-12 text-center">
            <h3 className="text-xl font-bold mb-2">No workflows yet</h3>
            <p className="text-gray-400 mb-6">
              Create your first workflow to automate business processes
            </p>
            <button
              onClick={() => setShowForm(true)}
              className="bg-cyan-500 hover:bg-cyan-600 text-black font-semibold py-2 px-6 rounded-lg inline-flex items-center gap-2 transition"
            >
              <Plus size={20} />
              Create Your First Workflow
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
