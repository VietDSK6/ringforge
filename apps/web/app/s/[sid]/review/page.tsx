import { Suspense } from "react";

import { PageSkeleton } from "@/components/PageSkeleton";
import { ReviewView } from "@/components/ReviewView";

export default function ReviewPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ReviewView />
    </Suspense>
  );
}
