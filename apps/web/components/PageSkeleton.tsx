/** Khung chờ khi trang/dữ liệu đang tải (docs/07 mục 5: skeleton thay vì chữ trơn). */
export function PageSkeleton({ label = "Đang tải…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-6">
      <span className="sr-only">{label}</span>
      <div aria-hidden className="space-y-3">
        <div className="h-7 w-56 animate-pulse rounded-md bg-sunken" />
        <div className="h-4 w-full max-w-xl animate-pulse rounded bg-sunken" />
      </div>
      <div aria-hidden className="panel divide-y divide-line">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="flex items-center gap-4 p-4">
            <div className="h-4 w-20 animate-pulse rounded bg-sunken" />
            <div className="h-4 flex-1 animate-pulse rounded bg-sunken" style={{ maxWidth: `${70 - i * 12}%` }} />
          </div>
        ))}
      </div>
      <p aria-hidden className="text-sm text-muted">
        {label}
      </p>
    </div>
  );
}
