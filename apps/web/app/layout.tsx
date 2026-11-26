import type { Metadata } from "next";

import { SandboxBanner } from "@/components/SandboxBanner";

import "./globals.css";

export const metadata: Metadata = {
  title: "RingForge",
  description: "CI/CD cho chính sách rủi ro — kiểm chứng hình thức bộ luật chống gian lận.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="flex min-h-full flex-col font-sans">
        <SandboxBanner />
        {children}
      </body>
    </html>
  );
}
