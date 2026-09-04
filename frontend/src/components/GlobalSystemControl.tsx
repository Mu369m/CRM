"use client";

import { useState } from "react";
import {
  AlertOctagon,
  Bell,
  Check,
  ChevronDown,
  Database,
  Info,
  LockKeyhole,
  Radio,
  Server,
  ShieldAlert,
  Users,
  X,
} from "lucide-react";

type BroadcastCategory = "MAINTENANCE" | "URGENT_NEWS" | "INFO";
type BroadcastTarget = "ALL_BROKERS";

const categoryStyles: Record<
  BroadcastCategory,
  { label: string; icon: typeof Info; className: string }
> = {
  MAINTENANCE: {
    label: "Maintenance",
    icon: Server,
    className: "system-ticker amber",
  },
  URGENT_NEWS: {
    label: "Urgent news",
    icon: ShieldAlert,
    className: "system-ticker red",
  },
  INFO: { label: "Information", icon: Info, className: "system-ticker blue" },
};

export default function GlobalSystemControl() {
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<BroadcastCategory>("MAINTENANCE");
  const [target, setTarget] = useState<BroadcastTarget>("ALL_BROKERS");
  const [enabled, setEnabled] = useState(false);
  const [locked, setLocked] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const style = categoryStyles[category];
  const Icon = style.icon;
  const previewMessage =
    message.trim() || "Your system announcement will appear here.";

  async function saveBroadcast() {
    setError("");
    try {
      const token = window.localStorage.getItem("access_token");
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/owner/broadcast`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            type: category,
            message: message.trim(),
            enabled,
            target_brokers: target,
          }),
        },
      );
      if (!response.ok) throw new Error("Broadcast save failed");
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Broadcast save failed",
      );
    }
  }

  return (
    <main className="system-control-page">
      <header className="system-control-header">
        <div>
          <p className="system-eyebrow">Master owner control</p>
          <h1>Global system control</h1>
          <p className="system-subtitle">
            Broadcast platform-wide notices and manage operational safety
            controls.
          </p>
        </div>
        <div className="owner-status">
          <span className="owner-status-dot" /> Production control plane
        </div>
      </header>

      <section
        className="system-section preview-section"
        aria-labelledby="preview-title"
      >
        <div className="system-section-heading">
          <div>
            <p className="system-eyebrow">Broker dashboard preview</p>
            <h2 id="preview-title">Live ticker strip</h2>
          </div>
          <span className="preview-live">
            <Radio size={14} /> Live preview
          </span>
        </div>
        <div
          className={`${style.className} ${enabled ? "is-enabled" : "is-disabled"}`}
        >
          <Icon size={17} aria-hidden="true" />
          <strong>{style.label}</strong>
          <span className="ticker-copy">{previewMessage}</span>
          <span className="ticker-target">{target.replaceAll("_", " ")}</span>
          <X size={15} aria-hidden="true" />
        </div>
        <p className="preview-note">
          This is the exact strip brokers will see when the broadcast is
          enabled.
        </p>
      </section>

      <div className="system-control-grid">
        <section
          className="system-section configurator"
          aria-labelledby="broadcast-title"
        >
          <div className="system-section-heading">
            <div>
              <p className="system-eyebrow">Broadcast configuration</p>
              <h2 id="broadcast-title">Prepare an announcement</h2>
            </div>
            <Bell size={19} />
          </div>
          <label className="system-label" htmlFor="broadcast-message">
            Announcement message
          </label>
          <textarea
            id="broadcast-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            maxLength={240}
            rows={4}
            placeholder="Scheduled DB Maintenance on Sunday at 02:00 UTC"
          />
          <div className="character-count">{message.length} / 240</div>
          <div className="system-field-grid">
            <label className="system-label">
              Category
              <select
                value={category}
                onChange={(event) =>
                  setCategory(event.target.value as BroadcastCategory)
                }
              >
                <option value="MAINTENANCE">Maintenance</option>
                <option value="URGENT_NEWS">Urgent news</option>
                <option value="INFO">Information</option>
              </select>
            </label>
            <label className="system-label">
              Visibility target
              <select
                value={target}
                onChange={(event) =>
                  setTarget(event.target.value as BroadcastTarget)
                }
              >
                <option value="ALL_BROKERS">All brokers</option>
              </select>
            </label>
          </div>
          {error && (
            <p className="system-error" role="alert">
              {error}
            </p>
          )}
          <div className="broadcast-actions">
            <button
              className={`switch ${enabled ? "on" : ""}`}
              type="button"
              aria-pressed={enabled}
              onClick={() => setEnabled((value) => !value)}
            >
              <span />
              {enabled ? "Broadcast enabled" : "Broadcast disabled"}
            </button>
            <button
              className="primary-action"
              type="button"
              onClick={saveBroadcast}
            >
              {saved ? (
                <>
                  <Check size={16} /> Saved
                </>
              ) : (
                "Save broadcast"
              )}
            </button>
          </div>
        </section>

        <section
          className={`system-section emergency-panel ${locked ? "locked" : ""}`}
          aria-labelledby="emergency-title"
        >
          <div className="emergency-icon">
            <LockKeyhole size={21} />
          </div>
          <p className="system-eyebrow">Emergency response</p>
          <h2 id="emergency-title">Platform kill-switch</h2>
          <p>
            Freeze new trading and administrative activity across every broker
            tenant. Existing sessions will be forced into read-only mode.
          </p>
          {locked ? (
            <div className="lock-confirmation">
              <Check size={17} /> Platform freeze requested
              <button type="button" onClick={() => setLocked(false)}>
                Release freeze
              </button>
            </div>
          ) : (
            <button
              className="danger-action"
              type="button"
              onClick={() => setLocked(true)}
            >
              <AlertOctagon size={17} /> Lock the platform
            </button>
          )}
        </section>
      </div>

      <section
        className="system-section metrics-section"
        aria-labelledby="metrics-title"
      >
        <div className="system-section-heading">
          <div>
            <p className="system-eyebrow">Master audit</p>
            <h2 id="metrics-title">System metrics</h2>
          </div>
          <span className="metrics-refresh">Live source required</span>
        </div>
        <div className="system-metrics-grid">
          <Metric icon={Users} label="Total active brokers" />
          <Metric icon={Database} label="Connected BYODB databases" />
          <Metric icon={Server} label="System health status" />
          <Metric icon={Radio} label="Active broadcast status" />
        </div>
      </section>
    </main>
  );
}

function Metric({ icon: Icon, label }: { icon: typeof Users; label: string }) {
  return (
    <article className="system-metric">
      <div className="metric-icon">
        <Icon size={18} />
      </div>
      <div>
        <p>{label}</p>
        <strong>Unavailable</strong>
        <small>Awaiting master API data</small>
      </div>
      <ChevronDown size={15} className="metric-chevron" />
    </article>
  );
}
