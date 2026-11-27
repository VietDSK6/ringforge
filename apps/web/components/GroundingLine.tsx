import { formatInt, formatVnd } from "@/lib/format";
import type { Grounding } from "@/lib/types";

/** Vùng vi phạm lớn cỡ nào trong dữ liệu (docs/07 mục 3.4). Số liệu do hệ thống tính, không phải AI. */
export function GroundingLine({ g, what = "rơi vào vùng vi phạm" }: { g: Grounding; what?: string }) {
  if (g.tx_count === 0) {
    return (
      <p className="rounded-xl border-2 border-amber-400 bg-amber-50 p-3 text-sm font-semibold text-amber-900 dark:bg-amber-950 dark:text-amber-200">
        0 giao dịch trong {g.days.length} ngày dữ liệu — backtest sẽ <u>không</u> phát hiện lỗi này. Chỉ kiểm chứng hình thức bắt được.
      </p>
    );
  }
  const scenarios = Object.entries(g.by_scenario);
  return (
    <div className="space-y-2 rounded-xl bg-background p-3 text-sm">
      <p>
        Trong {g.days.length} ngày dữ liệu tổng hợp:{" "}
        <strong className="tabular-nums">
          {formatInt(g.tx_count)} giao dịch · {formatVnd(g.amount_sum)}
        </strong>{" "}
        {what}. <span className="text-xs text-muted">(hệ thống tính)</span>
      </p>
      {scenarios.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Phân rã theo kịch bản">
          {scenarios.map(([key, s]) => (
            <li
              key={key}
              className={`rounded-full px-2.5 py-0.5 text-xs ${
                key === "S2_ATO" || key === "S1_MULE"
                  ? "bg-red-100 font-semibold text-danger dark:bg-red-950"
                  : "border border-line"
              }`}
            >
              {s.label_vi}: {formatInt(s.count)} · {formatVnd(s.amount_sum)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
