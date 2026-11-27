import { Suspense } from "react";

import { PageSkeleton } from "@/components/PageSkeleton";
import { CompareView } from "@/components/CompareView";

export default function ComparePage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <CompareView />
    </Suspense>
  );
}
