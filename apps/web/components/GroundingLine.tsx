import { Callout } from "@/components/Callout";
import { SourceTag } from "@/components/SourceTag";
import { formatInt, formatVnd } from "@/lib/format";
import type { Grounding } from "@/lib/types";

/** Vùng vi phạm lớn cỡ nào trong dữ liệu (docs/07 mục 3.4). Số liệu do hệ thống tính, không phải AI. */
export function GroundingLine({ g, what = "rơi vào vùng vi phạm" }: { g: Grounding; what?: string }) {
  if (g.tx_count === 0) {
    return (
      <Callout tone="warn" title={`0 giao dịch trong ${g.days.length} ngày dữ liệu`}>
        <p>
          Backtest sẽ <u>không</u> phát hiện lỗi này. Chỉ kiểm chứng hình thức bắt được.
        </p>
      </Callout>
    );
  }
  const scenarios = Object.entries(g.by_scenario);
  return (
    <div className="rounded-lg border border-line bg-sunken p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-muted">Trong {g.days.length} ngày dữ liệu tổng hợp</p>
        <SourceTag source="system" />
      </div>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-0.5">
        <strong className="num text-2xl font-bold tracking-tight">{formatInt(g.tx_count)} giao dịch</strong>
        <strong className="num text-2xl font-bold tracking-tight">{formatVnd(g.amount_sum)}</strong>
      </p>
      <p className="mt-0.5">{what}.</p>
      {scenarios.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Phân rã theo kịch bản">
          {scenarios.map(([key, s]) => (
            <li key={key} className={`chip num rounded-md ${key === "S2_ATO" || key === "S1_MULE" ? "tone-fail font-semibold" : ""}`}>
              {s.label_vi}: {formatInt(s.count)} · {formatVnd(s.amount_sum)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
