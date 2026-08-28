import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Northstar Brokerage CRM",
  description: "Operations command center for a multi-asset brokerage",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
