import { Suspense } from "react";

import { ReviewView } from "@/components/ReviewView";

export default function ReviewPage() {
  return (
    <Suspense fallback={<p className="text-muted">Đang tải…</p>}>
      <ReviewView />
    </Suspense>
  );
}
