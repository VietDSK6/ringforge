import { Suspense } from "react";

import { PageSkeleton } from "@/components/PageSkeleton";
import { StudioView } from "@/components/StudioView";

export default function StudioPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <StudioView />
    </Suspense>
  );
}
