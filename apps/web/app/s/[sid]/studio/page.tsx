import { Suspense } from "react";

import { StudioView } from "@/components/StudioView";

export default function StudioPage() {
  return (
    <Suspense fallback={<p className="text-muted">Đang tải…</p>}>
      <StudioView />
    </Suspense>
  );
}
