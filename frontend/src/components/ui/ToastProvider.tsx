"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; message: string; tone: "success" | "error" };
const ToastContext = createContext<(message: string, tone?: Toast["tone"]) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const show = (message: string, tone: Toast["tone"] = "success") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), 3000);
  };
  return <ToastContext.Provider value={show}>{children}<div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">{items.map((item) => <div className={`pointer-events-auto rounded-md border px-4 py-3 text-sm shadow-2xl backdrop-blur ${item.tone === "error" ? "border-rose-500/40 bg-rose-950/90 text-rose-100" : "border-emerald-500/40 bg-emerald-950/90 text-emerald-100"}`} key={item.id}>{item.message}</div>)}</div></ToastContext.Provider>;
}

export const useToast = () => useContext(ToastContext);
