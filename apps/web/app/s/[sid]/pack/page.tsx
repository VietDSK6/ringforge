import { Suspense } from "react";

import { PageSkeleton } from "@/components/PageSkeleton";
import { PackView } from "@/components/PackView";

export default function PackPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <PackView />
    </Suspense>
  );
}
