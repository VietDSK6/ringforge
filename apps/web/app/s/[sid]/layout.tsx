import Link from "next/link";
import { Suspense } from "react";

import { SessionNav } from "@/components/SessionNav";

export default function SessionLayout({ children }: LayoutProps<"/s/[sid]">) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 pb-24 pt-4 md:flex-row md:pb-10">
      <div className="md:w-52 md:shrink-0">
        <Link href="/" className="mb-4 hidden text-lg font-bold tracking-tight md:block">
          RingForge
        </Link>
        {/* useParams treo khi tham số động chưa biết lúc prerender → cần Suspense (cacheComponents). */}
        <Suspense fallback={null}>
          <SessionNav />
        </Suspense>
      </div>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
