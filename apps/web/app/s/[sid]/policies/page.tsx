import { Suspense } from "react";

import { PageSkeleton } from "@/components/PageSkeleton";
import { PoliciesView } from "@/components/PoliciesView";

export default function PoliciesPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <PoliciesView />
    </Suspense>
  );
}
