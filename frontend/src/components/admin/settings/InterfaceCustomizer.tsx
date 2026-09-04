"use client";

import { useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import {
  Check,
  LayoutDashboard,
  Menu,
  Monitor,
  Smartphone,
  Sparkles,
  Zap,
} from "lucide-react";
import { useTenant } from "@/context/TenantContext";

type ThemePreset = "dark" | "glass" | "solid" | "custom";
type PreviewDevice = "desktop" | "mobile";
type MobileNavigation = "bottom-bar" | "drawer";
type DesktopDensity = "compact" | "spaced";

export interface InterfaceCustomizerConfig {
  theme: ThemePreset;
  primaryColor: string;
  mobileNavigation: MobileNavigation;
  desktopDensity: DesktopDensity;
  showQuickActions: boolean;
  logoUrl: string;
  faviconUrl: string;
  appName: string;
}

export interface InterfaceCustomizerProps {
  scope?: "owner" | "admin";
  initialConfig?: Partial<InterfaceCustomizerConfig>;
  onPublish?: (config: InterfaceCustomizerConfig) => void;
}

const defaultConfig: InterfaceCustomizerConfig = {
  theme: "glass",
  primaryColor: "#42d3ae",
  mobileNavigation: "bottom-bar",
  desktopDensity: "spaced",
  showQuickActions: true,
  logoUrl: "",
  faviconUrl: "",
  appName: "Northstar Markets",
};

const presets: Array<{
  id: ThemePreset;
  label: string;
  detail: string;
  color: string;
}> = [
  {
    id: "dark",
    label: "Midnight",
    detail: "Focused and quiet",
    color: "#60a5fa",
  },
  {
    id: "glass",
    label: "Glass",
    detail: "Soft translucent panels",
    color: "#42d3ae",
  },
  {
    id: "solid",
    label: "Solid",
    detail: "High contrast surfaces",
    color: "#f59e0b",
  },
];

export default function InterfaceCustomizer({
  scope = "admin",
  initialConfig,
  onPublish,
}: InterfaceCustomizerProps) {
  const { branding } = useTenant();
  const [config, setConfig] = useState<InterfaceCustomizerConfig>({
    ...defaultConfig,
    ...initialConfig,
  });
  const [device, setDevice] = useState<PreviewDevice>("desktop");
  const [status, setStatus] = useState("Unsaved changes");
  const [saving, setSaving] = useState(false);
  const setValue = <Key extends keyof InterfaceCustomizerConfig>(
    key: Key,
    value: InterfaceCustomizerConfig[Key],
  ) => {
    setStatus("Unsaved changes");
    setConfig((current) => ({ ...current, [key]: value }));
  };

  useEffect(() => {
    const token = window.localStorage.getItem("access_token");
    if (!token) {
      if (branding)
        Promise.resolve().then(() =>
          setConfig((current) => ({
            ...current,
            appName: branding.companyName || current.appName,
            primaryColor: branding.primaryColor,
            logoUrl: branding.logoUrl ?? "",
            faviconUrl: branding.faviconUrl ?? "",
          })),
        );
      return;
    }
    const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${api}/api/v1/broker/settings/theme`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) =>
        response.ok
          ? (response.json() as Promise<{
              draft?: { config?: Record<string, unknown> };
            }>)
          : null,
      )
      .then((data) => {
        const theme = data?.draft?.config;
        if (!theme) return;
        setConfig((current) => ({
          ...current,
          appName: String(theme.company_name ?? current.appName),
          primaryColor: String(theme.primary_color ?? current.primaryColor),
          logoUrl: String(theme.logo_url ?? ""),
          faviconUrl: String(theme.favicon_url ?? ""),
        }));
        setStatus("Draft loaded");
      })
      .catch(() => setStatus("Unable to load saved theme"));
  }, [branding]);

  useEffect(() => {
    if (config.appName) document.title = config.appName;
    if (config.faviconUrl) {
      const favicon =
        document.querySelector<HTMLLinkElement>('link[rel="icon"]') ??
        document.createElement("link");
      favicon.rel = "icon";
      favicon.href = config.faviconUrl;
      document.head.appendChild(favicon);
    }
  }, [config.appName, config.faviconUrl]);

  async function publish() {
    setSaving(true);
    setStatus("Publishing...");
    const token = window.localStorage.getItem("access_token");
    const broadcast = () => {
      const channel =
        "BroadcastChannel" in window
          ? new BroadcastChannel("tenant-theme")
          : null;
      channel?.postMessage({
        type: "theme_updated",
        branding: {
          companyName: config.appName,
          primaryColor: config.primaryColor,
          secondaryColor: "#1d3430",
          logoUrl: config.logoUrl || undefined,
          faviconUrl: config.faviconUrl || undefined,
          metaTitle: config.appName,
        },
      });
      channel?.close();
    };
    try {
      if (token) {
        const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const draftResponse = await fetch(
          `${api}/api/v1/broker/settings/theme/draft`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              config: {
                mode: config.theme === "dark" ? "dark" : "system",
                primary_color: config.primaryColor,
                secondary_color: "#1d3430",
                logo_url: config.logoUrl || null,
                favicon_url: config.faviconUrl || null,
                company_name: config.appName,
                preset:
                  config.theme === "glass"
                    ? "modern"
                    : config.theme === "solid"
                      ? "classic"
                      : "professional",
              },
            }),
          },
        );
        if (!draftResponse.ok) throw new Error("Theme draft was rejected");
        const response = await fetch(
          `${api}/api/v1/broker/settings/theme/publish`,
          { method: "POST", headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) throw new Error("Theme publish was rejected");
      }
      onPublish?.(config);
      broadcast();
      setStatus(token ? "Published live" : "Saved on this device");
    } catch (error) {
      setStatus(
        error instanceof Error
          ? `${error.message}; local preview saved`
          : "Local preview saved",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#071016] px-4 py-6 text-slate-100 sm:px-6 lg:px-10 lg:py-10">
      <div className="mx-auto max-w-[1440px]">
        <header className="mb-8 flex flex-col justify-between gap-5 border-b border-white/10 pb-7 sm:flex-row sm:items-end">
          <div>
            <p className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#42d3ae]">
              <Sparkles size={13} />{" "}
              {scope === "owner" ? "Owner workspace" : "Broker administration"}
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Interface customizer
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
              Shape the experience your traders see. Every adjustment is
              reflected in the preview instantly.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`text-xs ${status === "Published live" || status === "Saved on this device" ? "text-emerald-300" : "text-slate-500"}`}
            >
              {status}
            </span>
            <button
              type="button"
              disabled={saving}
              onClick={() => void publish()}
              className="flex items-center gap-2 rounded-md bg-[#42d3ae] px-4 py-2.5 text-xs font-bold text-[#061812] transition hover:bg-[#72e6c6] disabled:cursor-wait disabled:opacity-60"
            >
              <Zap size={14} /> {saving ? "Publishing..." : "Publish changes"}
            </button>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <section className="space-y-5" aria-label="Customizer controls">
            <ControlSection title="Theme direction" kicker="01">
              <div className="grid gap-2">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      setValue("theme", preset.id);
                      setValue("primaryColor", preset.color);
                    }}
                    className={`flex items-center gap-3 rounded-md border p-3 text-left transition ${config.theme === preset.id ? "border-[#42d3ae]/70 bg-[#42d3ae]/10" : "border-white/10 bg-white/[0.03] hover:border-white/25"}`}
                  >
                    <span
                      className="size-8 rounded border border-white/20"
                      style={{
                        background: `linear-gradient(135deg, ${preset.color}, #101b24)`,
                      }}
                    />
                    <span className="min-w-0 flex-1">
                      <strong className="block text-xs text-white">
                        {preset.label}
                      </strong>
                      <small className="mt-0.5 block text-[10px] text-slate-500">
                        {preset.detail}
                      </small>
                    </span>
                    {config.theme === preset.id && (
                      <Check size={15} className="text-[#42d3ae]" />
                    )}
                  </button>
                ))}
              </div>
              <label className="mt-4 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Custom primary color
                <input
                  aria-label="Custom primary color"
                  type="color"
                  value={config.primaryColor}
                  onChange={(event) => {
                    setValue("primaryColor", event.target.value);
                    setValue("theme", "custom");
                  }}
                  className="mt-2 h-10 w-full cursor-pointer rounded border border-white/10 bg-[#101b24] p-1"
                />
              </label>
            </ControlSection>

            <ControlSection title="Responsive behavior" kicker="02">
              <ToggleGroup
                label="Mobile navigation"
                options={[
                  { value: "bottom-bar", label: "Bottom bar" },
                  { value: "drawer", label: "Drawer" },
                ]}
                value={config.mobileNavigation}
                onChange={(value) =>
                  setValue("mobileNavigation", value as MobileNavigation)
                }
              />
              <ToggleGroup
                label="Desktop grid density"
                options={[
                  { value: "compact", label: "Compact" },
                  { value: "spaced", label: "Spaced" },
                ]}
                value={config.desktopDensity}
                onChange={(value) =>
                  setValue("desktopDensity", value as DesktopDensity)
                }
              />
              <SwitchRow
                label="Quick action row"
                detail="Show shortcuts above account activity"
                checked={config.showQuickActions}
                onChange={(event) =>
                  setValue("showQuickActions", event.target.checked)
                }
              />
            </ControlSection>

            <ControlSection title="Brand identity" kicker="03">
              <TextField
                label="App name"
                value={config.appName}
                placeholder="Northstar Markets"
                onChange={(event) => setValue("appName", event.target.value)}
              />
              <TextField
                label="Broker logo URL"
                value={config.logoUrl}
                placeholder="https://.../logo.svg"
                onChange={(event) => setValue("logoUrl", event.target.value)}
              />
              <TextField
                label="Favicon URL"
                value={config.faviconUrl}
                placeholder="https://.../favicon.png"
                onChange={(event) => setValue("faviconUrl", event.target.value)}
              />
            </ControlSection>
          </section>

          <section className="min-w-0" aria-label="Live device preview">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                  Live preview
                </p>
                <p className="mt-1 text-sm text-slate-300">
                  {device === "desktop" ? "Desktop window" : "Mobile phone"}{" "}
                  <span className="text-slate-600">/</span>{" "}
                  {config.appName || "Your application"}
                </p>
              </div>
              <div className="flex rounded-md border border-white/10 bg-white/[0.03] p-1">
                <DeviceButton
                  active={device === "desktop"}
                  label="Desktop"
                  icon={<Monitor size={14} />}
                  onClick={() => setDevice("desktop")}
                />
                <DeviceButton
                  active={device === "mobile"}
                  label="Mobile"
                  icon={<Smartphone size={14} />}
                  onClick={() => setDevice("mobile")}
                />
              </div>
            </div>
            <Preview device={device} config={config} />
          </section>
        </div>
      </div>
    </main>
  );
}

function ControlSection({
  title,
  kicker,
  children,
}: {
  title: string;
  kicker: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-[#0c171e] p-5 shadow-2xl shadow-black/10">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-[10px] font-bold text-[#42d3ae]">{kicker}</span>
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      {children}
    </section>
  );
}
function TextField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="mt-3 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
      {label}
      <input
        value={value}
        placeholder={placeholder}
        onChange={onChange}
        className="mt-2 w-full rounded border border-white/10 bg-[#071016] px-3 py-2.5 text-xs font-normal normal-case tracking-normal text-slate-200 outline-none placeholder:text-slate-700 focus:border-[#42d3ae]/60"
      />
    </label>
  );
}
function ToggleGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="mb-5">
      <span className="mb-2 block text-[11px] text-slate-400">{label}</span>
      <div className="grid grid-cols-2 rounded border border-white/10 bg-[#071016] p-1">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded px-2 py-2 text-[11px] transition ${value === option.value ? "bg-white/10 font-semibold text-white" : "text-slate-500 hover:text-slate-300"}`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
function SwitchRow({
  label,
  detail,
  checked,
  onChange,
}: {
  label: string;
  detail: string;
  checked: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4">
      <span>
        <span className="block text-[11px] text-slate-300">{label}</span>
        <small className="mt-1 block text-[10px] text-slate-600">
          {detail}
        </small>
      </span>
      <span
        className={`relative h-5 w-9 shrink-0 rounded-full transition ${checked ? "bg-[#42d3ae]" : "bg-slate-700"}`}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={onChange}
          className="peer sr-only"
        />
        <span className="absolute left-1 top-1 size-3 rounded-full bg-white transition peer-checked:translate-x-4" />
      </span>
    </label>
  );
}
function DeviceButton({
  active,
  label,
  icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] ${active ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}
    >
      {icon}
      {label}
    </button>
  );
}

function Preview({
  device,
  config,
}: {
  device: PreviewDevice;
  config: InterfaceCustomizerConfig;
}) {
  const isGlass = config.theme === "glass";
  const surface =
    config.theme === "solid"
      ? "#17232a"
      : isGlass
        ? "rgba(21, 38, 45, .72)"
        : "#0e1920";
  const spacing = config.desktopDensity === "compact" ? "gap-2" : "gap-4";
  const logo = config.logoUrl ? (
    <span
      role="img"
      aria-label="Broker logo"
      className="size-6 rounded bg-contain bg-center bg-no-repeat"
      style={{ backgroundImage: `url(${config.logoUrl})` }}
    />
  ) : (
    <span className="grid size-6 place-items-center rounded bg-[var(--preview-primary)] text-[10px] font-bold text-[#061812]">
      N
    </span>
  );
  return (
    <div
      className={`mx-auto overflow-hidden border border-white/15 bg-[#0a141a] shadow-2xl shadow-black/30 transition-all duration-300 ${device === "mobile" ? "max-w-[390px] rounded-[30px] border-[7px] border-[#1f2c32]" : "rounded-xl"}`}
      style={{ ["--preview-primary" as string]: config.primaryColor }}
    >
      <div className="flex h-8 items-center gap-1 border-b border-white/10 bg-[#101d24] px-3">
        <span className="size-1.5 rounded-full bg-rose-400/70" />
        <span className="size-1.5 rounded-full bg-amber-300/70" />
        <span className="size-1.5 rounded-full bg-emerald-300/70" />
        <span className="ml-2 flex-1 rounded bg-white/5 px-3 py-1 text-center text-[8px] text-slate-600">
          app.yourbroker.com
        </span>
      </div>
      <div
        className="min-h-[600px]"
        style={{
          background: isGlass
            ? "linear-gradient(135deg, #0d1b20, #091217 60%, #10241f)"
            : "#091218",
        }}
      >
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div className="flex items-center gap-2">
            {logo}
            <span className="text-xs font-semibold text-white">
              {config.appName || "Your application"}
            </span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-slate-500">
            <span className="hidden sm:inline">Markets</span>
            <span className="hidden sm:inline">Wallet</span>
            <span className="grid size-6 place-items-center rounded-full bg-white/10 text-[9px] text-slate-300">
              RK
            </span>
          </div>
        </header>
        <div
          className={`grid ${device === "mobile" ? "grid-cols-1" : "grid-cols-[150px_1fr]"}`}
        >
          <aside
            className={`${device === "mobile" ? "hidden" : "border-r border-white/10"} min-h-[520px] p-4`}
          >
            <p className="mb-4 text-[9px] uppercase tracking-widest text-slate-600">
              Workspace
            </p>
            {["Overview", "Trading", "Wallet", "Reports"].map((item, index) => (
              <div
                key={item}
                className={`mb-1 rounded px-3 py-2 text-[10px] ${index === 0 ? "bg-[var(--preview-primary)]/10 text-[var(--preview-primary)]" : "text-slate-500"}`}
              >
                {item}
              </div>
            ))}
          </aside>
          <div className="p-5">
            <div className="mb-5 flex items-end justify-between">
              <div>
                <p className="mb-1 text-[9px] uppercase tracking-widest text-slate-600">
                  Trader cabinet
                </p>
                <h3 className="text-lg font-semibold text-white">
                  Good morning, Riley
                </h3>
              </div>
              <button className="hidden rounded bg-[var(--preview-primary)] px-3 py-2 text-[10px] font-bold text-[#061812] sm:block">
                Deposit funds
              </button>
            </div>
            {config.showQuickActions && (
              <div className="mb-5 flex gap-2 overflow-hidden">
                <QuickAction label="Deposit" />
                <QuickAction label="Withdraw" />
                <QuickAction label="Transfer" />
              </div>
            )}
            <div className={`grid grid-cols-2 ${spacing}`}>
              <Metric label="Available balance" value="$24,680.40" accent />
              <Metric label="Open positions" value="08" />
              <Metric label="Today's P&L" value="+$842.16" />
            </div>
            <div
              className="mt-5 rounded border border-white/10 p-4"
              style={{ background: surface }}
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="text-xs font-semibold text-white">
                  Recent activity
                </span>
                <span className="text-[10px] text-[var(--preview-primary)]">
                  View all
                </span>
              </div>
              {[
                "EUR/USD · Buy 0.50 lot",
                "US 500 · Sell 1.00 lot",
                "BTC/USD · Buy 0.10 lot",
              ].map((item, index) => (
                <div
                  key={item}
                  className="flex items-center justify-between border-t border-white/5 py-3 text-[10px] text-slate-400"
                >
                  <span>{item}</span>
                  <strong
                    className={
                      index === 1 ? "text-rose-300" : "text-emerald-300"
                    }
                  >
                    {index === 1
                      ? "-$124.00"
                      : "+$" + (284 - index * 77) + ".00"}
                  </strong>
                </div>
              ))}
            </div>
            <div
              className="mt-5 rounded border border-white/10 p-4"
              style={{ background: surface }}
            >
              <p className="mb-3 text-[9px] uppercase tracking-widest text-slate-600">
                Login page
              </p>
              <div className="mx-auto max-w-[260px]">
                <h4 className="text-sm font-semibold text-white">
                  Welcome back
                </h4>
                <p className="mt-1 text-[10px] text-slate-500">
                  Sign in to your trading workspace
                </p>
                <div className="mt-4 space-y-2">
                  <div className="rounded border border-white/10 bg-black/10 px-3 py-2 text-[10px] text-slate-600">
                    Email address
                  </div>
                  <div className="rounded border border-white/10 bg-black/10 px-3 py-2 text-[10px] text-slate-600">
                    Password
                  </div>
                  <button className="w-full rounded bg-[var(--preview-primary)] py-2 text-[10px] font-bold text-[#061812]">
                    Continue
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        {device === "mobile" && (
          <nav className="sticky bottom-0 flex justify-around border-t border-white/10 bg-[#101d24] px-2 py-3 text-[9px] text-slate-500">
            {config.mobileNavigation === "bottom-bar" ? (
              ["Home", "Trade", "Wallet", "Profile"].map((item, index) => (
                <span
                  key={item}
                  className={index === 0 ? "text-[var(--preview-primary)]" : ""}
                >
                  {item}
                </span>
              ))
            ) : (
              <>
                <Menu size={15} className="text-[var(--preview-primary)]" />
                <span>Swipe for navigation drawer</span>
              </>
            )}
          </nav>
        )}
      </div>
    </div>
  );
}
function Metric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] p-3">
      <p className="text-[9px] text-slate-600">{label}</p>
      <strong
        className={`mt-2 block text-sm ${accent ? "text-[var(--preview-primary)]" : "text-slate-200"}`}
      >
        {value}
      </strong>
    </div>
  );
}
function QuickAction({ label }: { label: string }) {
  return (
    <button className="shrink-0 rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-[10px] text-slate-400">
      <LayoutDashboard size={11} className="mr-1 inline" />
      {label}
    </button>
  );
}
