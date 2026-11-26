import { Suspense } from "react";

import { PoliciesView } from "@/components/PoliciesView";

export default function PoliciesPage() {
  return (
    <Suspense fallback={<p className="text-muted">Đang tải…</p>}>
      <PoliciesView />
    </Suspense>
  );
}
