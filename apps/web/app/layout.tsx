import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { SandboxBanner } from "@/components/SandboxBanner";

import "./globals.css";

// IBM Plex Sans: dấu tiếng Việt rõ, có số tabular (tnum) để số tiền thẳng cột. IBM Plex Mono: mã luật, trường DSL, JSON. Cả hai SIL OFL 1.1.
const sans = IBM_Plex_Sans({
  subsets: ["latin", "vietnamese"],
  variable: "--font-plex-sans",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "RingForge",
  description: "CI/CD cho chính sách rủi ro — kiểm chứng hình thức bộ luật chống gian lận.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <SandboxBanner />
        {children}
      </body>
    </html>
  );
}
