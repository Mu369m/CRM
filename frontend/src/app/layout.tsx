import type { Metadata } from "next";
import "./globals.css";
import "../styles/design-tokens.css";
import { Providers } from "./providers";
import ServiceWorkerRegistration from "@/components/pwa/ServiceWorkerRegistration";

export const metadata: Metadata = {
  title: "Northstar Brokerage CRM",
  description: "Operations command center for a multi-asset brokerage",
  manifest: "/manifest.json",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <ServiceWorkerRegistration />
          {children}
        </Providers>
      </body>
    </html>
  );
}
