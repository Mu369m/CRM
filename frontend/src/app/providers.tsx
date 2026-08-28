"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { TenantProvider } from "./tenant-provider";
import { ToastProvider } from "@/components/ui/ToastProvider";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 2 } } }));
  return <QueryClientProvider client={queryClient}><TenantProvider><ToastProvider>{children}</ToastProvider></TenantProvider></QueryClientProvider>;
}
