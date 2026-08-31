"use client";

import { useState, useEffect } from "react";
import { Upload, FileText, Check, Clock, X, Download } from "lucide-react";
import MainLayout from "@/components/navigation/MainLayout";

interface KYCDocument {
  id: string;
  client_id: string;
  client_name: string;
  document_type: string;
  file_name: string;
  status: "PENDING" | "VERIFIED" | "REJECTED";
  uploaded_at: string;
  verified_at?: string;
}

interface KYCPage {
  items: KYCDocument[];
  total: number;
}

export default function KYCDocumentsPage() {
  const [documents, setDocuments] = useState<KYCDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [message, setMessage] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);

  const limit = 20;

  useEffect(() => {
    loadDocuments();
  }, [offset, statusFilter]);

  async function loadDocuments() {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
        ...(statusFilter !== "ALL" && { status: statusFilter }),
      });

      const response = await fetch(`/api/v1/broker/kyc-documents?${query}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to load");
      const data: KYCPage = await response.json();
      setDocuments(data.items);
      setTotal(data.total);
    } catch (e) {
      setMessage((e instanceof Error ? e.message : "Error loading") + " ❌");
    } finally {
      setLoading(false);
    }
  }

  async function verifyDocument(id: string) {
    try {
      const response = await fetch(`/api/v1/broker/kyc-documents/${id}/verify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to verify");
      setMessage("Document verified ✓");
      loadDocuments();
    } catch {
      setMessage("Failed to verify ❌");
    }
  }

  async function rejectDocument(id: string) {
    try {
      const response = await fetch(`/api/v1/broker/kyc-documents/${id}/reject`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to reject");
      setMessage("Document rejected");
      loadDocuments();
    } catch {
      setMessage("Failed to reject ❌");
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case "PENDING":
        return "bg-amber-400/10 text-amber-300";
      case "VERIFIED":
        return "bg-emerald-400/10 text-emerald-300";
      case "REJECTED":
        return "bg-rose-400/10 text-rose-300";
      default:
        return "bg-slate-400/10 text-slate-300";
    }
  };

  return (
    <MainLayout>
      <main className="mx-auto max-w-6xl">
        <header className="mb-7">
          <p className="text-[10px] uppercase tracking-[.2em] text-cyan-400">Compliance & KYC</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">KYC Documents</h1>
          <p className="mt-2 text-sm text-slate-500">Review and verify client KYC documentation.</p>
        </header>

        {message && (
          <div className="mb-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
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
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
          </select>

          <button
            onClick={() => setShowUploadModal(true)}
            className="rounded-md bg-cyan-400 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-cyan-500"
          >
            <Upload size={14} className="mr-1 inline" /> Upload Document
          </button>
        </div>

        <div className="overflow-hidden rounded-lg border border-slate-800 bg-[#0D121F]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Client</th>
                <th className="px-6 py-3 font-medium">Document Type</th>
                <th className="px-6 py-3 font-medium">File</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Uploaded</th>
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
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    No documents found.
                  </td>
                </tr>
              ) : (
                documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-800/30">
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">{doc.client_name}</div>
                      <div className="text-[10px] font-mono text-slate-500">{doc.client_id.slice(0, 8)}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-300">{doc.document_type}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-[10px] text-slate-400">
                        <FileText size={14} />
                        {doc.file_name}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`rounded px-2 py-1 text-[10px] font-medium ${statusColor(doc.status)}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-[10px] text-slate-500">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {doc.status === "PENDING" ? (
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => verifyDocument(doc.id)}
                            className="rounded border border-emerald-500/30 px-2 py-1 text-[10px] text-emerald-300 hover:bg-emerald-500/10"
                          >
                            <Check size={12} className="inline mr-1" /> Verify
                          </button>
                          <button
                            onClick={() => rejectDocument(doc.id)}
                            className="rounded border border-rose-500/30 px-2 py-1 text-[10px] text-rose-300 hover:bg-rose-500/10"
                          >
                            <X size={12} className="inline mr-1" /> Reject
                          </button>
                        </div>
                      ) : (
                        <button className="rounded border border-slate-600 px-2 py-1 text-[10px] text-slate-400">
                          <Download size={12} className="inline mr-1" /> Download
                        </button>
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
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Pending Review</p>
            <strong className="mt-2 block text-2xl text-amber-300">24</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Verified</p>
            <strong className="mt-2 block text-2xl text-emerald-300">892</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Rejected</p>
            <strong className="mt-2 block text-2xl text-rose-300">18</strong>
          </div>
          <div className="rounded-lg border border-slate-800 bg-[#0D121F] p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Completion Rate</p>
            <strong className="mt-2 block text-2xl text-cyan-300">96.2%</strong>
          </div>
        </div>

        {showUploadModal && (
          <KYCUploadModal
            onClose={() => setShowUploadModal(false)}
            onUpload={() => {
              setShowUploadModal(false);
              loadDocuments();
            }}
          />
        )}
      </main>
    </MainLayout>
  );
}

function KYCUploadModal({ onClose, onUpload }: { onClose: () => void; onUpload: () => void }) {
  const [clientId, setClientId] = useState("");
  const [docType, setDocType] = useState("ID");
  const [uploading, setUploading] = useState(false);

  async function submit() {
    if (!clientId.trim()) {
      alert("Please enter client ID");
      return;
    }

    setUploading(true);
    try {
      const response = await fetch("/api/v1/broker/kyc-documents", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          client_id: clientId,
          document_type: docType,
          file_url: "https://example.com/document.pdf",
        }),
      });

      if (!response.ok) throw new Error("Upload failed");
      onUpload();
    } catch (e) {
      alert((e instanceof Error ? e.message : "Upload error") + " ❌");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-lg border border-slate-700 bg-[#0D121F] p-6">
        <h2 className="text-lg font-semibold text-white">Upload KYC Document</h2>

        <div className="mt-6 space-y-4">
          <div>
            <label className="text-xs text-slate-400">Client ID</label>
            <input
              type="text"
              placeholder="client-xxx"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            />
          </div>

          <div>
            <label className="text-xs text-slate-400">Document Type</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-[#070A11] px-3 py-2 text-sm text-slate-200"
            >
              <option>ID</option>
              <option>Passport</option>
              <option>Driver License</option>
              <option>Proof of Address</option>
              <option>Source of Funds</option>
            </select>
          </div>

          <div className="rounded-lg border-2 border-dashed border-slate-600 px-6 py-8 text-center">
            <Upload size={32} className="mx-auto mb-2 text-slate-500" />
            <p className="text-xs text-slate-400">Click to select file or drag and drop</p>
          </div>
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
            disabled={uploading}
            className="flex-1 rounded-md bg-cyan-400 px-4 py-2 text-xs font-bold text-slate-950 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
