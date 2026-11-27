import { Suspense } from "react";

import { PackView } from "@/components/PackView";

export default function PackPage() {
  return (
    <Suspense fallback={<p className="text-muted">Đang tải…</p>}>
      <PackView />
    </Suspense>
  );
}
