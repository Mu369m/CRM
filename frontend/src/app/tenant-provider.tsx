"use client";

import { useEffect, type ReactNode } from "react";

interface TenantSettings {
  primary_color: string;
  secondary_color: string;
  logo_url?: string | null;
  favicon_url?: string | null;
  meta_title: string;
  support_email?: string | null;
}

export function TenantProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const token = window.localStorage.getItem("access_token");
    if (!token) return;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiUrl}/api/settings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.json() : null))
      .then((settings: TenantSettings | null) => {
        if (!settings) return;
        const root = document.documentElement;
        root.style.setProperty("--tenant-primary", settings.primary_color);
        root.style.setProperty("--tenant-secondary", settings.secondary_color);
        document.title = settings.meta_title;
        if (settings.favicon_url) {
          const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]') ?? document.createElement("link");
          favicon.rel = "icon";
          favicon.href = settings.favicon_url;
          document.head.appendChild(favicon);
        }
      })
      .catch(() => undefined);
  }, []);

  return children;
}
