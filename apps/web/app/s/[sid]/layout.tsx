import { Suspense } from "react";

import { AiStatusBanner } from "@/components/AiStatusBanner";
import { Logo } from "@/components/Logo";
import { SessionNav } from "@/components/SessionNav";
import { StatusPill } from "@/components/StatusPill";

export default function SessionLayout({ children }: LayoutProps<"/s/[sid]">) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-[90rem] flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-1.5 md:px-6">
          <Logo />
          <StatusPill />
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-[90rem] flex-1 flex-col gap-6 px-4 pb-28 pt-6 md:flex-row md:gap-8 md:px-6 md:pb-12">
        {/* useParams treo khi tham số động chưa biết lúc prerender → cần Suspense (cacheComponents). */}
        <Suspense fallback={<div className="hidden md:block md:w-52 md:shrink-0" />}>
          <SessionNav />
        </Suspense>
        <main className="min-w-0 flex-1 space-y-4">
          <AiStatusBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
