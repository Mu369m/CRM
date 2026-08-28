"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface TenantBranding {
  companyName: string;
  primaryColor: string;
  secondaryColor: string;
  logoUrl?: string;
  faviconUrl?: string;
  metaTitle?: string;
  supportEmail?: string | null;
}

const TenantContext = createContext<{ branding: TenantBranding | null }>({ branding: null });

export function TenantProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<TenantBranding | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const domain = window.location.hostname;
    fetch(`${apiUrl}/api/v1/tenant/config?domain=${encodeURIComponent(domain)}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((settings: { company_name: string; primary_color: string; secondary_color: string; logo_url?: string | null; favicon_url?: string | null; meta_title: string; support_email?: string | null } | null) => {
        if (!settings) throw new Error("Tenant branding unavailable");
        const nextBranding: TenantBranding = { companyName: settings.company_name, primaryColor: settings.primary_color, secondaryColor: settings.secondary_color, logoUrl: settings.logo_url ?? undefined, faviconUrl: settings.favicon_url ?? undefined, metaTitle: settings.meta_title, supportEmail: settings.support_email };
        setBranding(nextBranding);
        const root = document.documentElement;
        root.style.setProperty("--primary", nextBranding.primaryColor);
        root.style.setProperty("--secondary", nextBranding.secondaryColor);
        root.style.setProperty("--tenant-primary", nextBranding.primaryColor);
        root.style.setProperty("--tenant-secondary", nextBranding.secondaryColor);
        document.title = nextBranding.metaTitle ?? nextBranding.companyName;
        if (nextBranding.faviconUrl) {
          const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]') ?? document.createElement("link");
          favicon.rel = "icon";
          favicon.href = nextBranding.faviconUrl;
          document.head.appendChild(favicon);
        }
      })
      .catch(() => {
        document.documentElement.style.setProperty("--primary", "#0F172A");
        document.documentElement.style.setProperty("--secondary", "#3B82F6");
      });
  }, []);

  return <TenantContext.Provider value={{ branding }}>{children}</TenantContext.Provider>;
}

export const useTenant = () => useContext(TenantContext);
