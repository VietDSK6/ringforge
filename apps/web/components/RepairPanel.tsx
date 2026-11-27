import { CandidateCard } from "@/components/CandidateCard";
import type { RepairCandidate, RepairResponse } from "@/lib/types";

const LLM_NOTE: Partial<Record<RepairResponse["llm"], string>> = {
  unavailable: "AI hiện không khả dụng — chỉ có bản sửa tất định.",
  quota: "Đã hết lượt gọi AI hôm nay — chỉ có bản sửa tất định.",
  error: "Gọi AI bị lỗi — chỉ có bản sửa tất định.",
};

export function RepairPanel({
  data,
  onUse,
  busy,
}: {
  data: RepairResponse;
  onUse: (c: RepairCandidate) => void;
  busy: boolean;
}) {
  if (data.needed === false) {
    return <p className="rounded-xl border border-line bg-surface p-4 text-sm">{data.message_vi}</p>;
  }
  return (
    <section aria-labelledby="repair-title" className="space-y-4">
      <h2 id="repair-title" className="text-lg font-semibold">
        Bản sửa đề xuất — mọi bản đều đã được kiểm chứng lại và backtest
      </h2>
      {LLM_NOTE[data.llm] && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {LLM_NOTE[data.llm]}
        </p>
      )}
      {data.candidates.length === 0 && (
        <p className="text-sm">Chưa có bản sửa nào qua kiểm chứng. Hãy thử viết lại luật.</p>
      )}
      {data.candidates.map((c) => (
        <CandidateCard key={`${c.source}-${c.rank}`} c={c} onUse={onUse} busy={busy} />
      ))}
      {data.rejected.length > 0 && (
        <details className="text-sm text-muted">
          <summary className="cursor-pointer">
            {data.rejected.length} đề xuất khác bị loại vì không qua kiểm chứng (bấm xem lý do)
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {data.rejected.map((r, i) => (
              <li key={i}>
                {r.source === "ai" ? "AI" : "Tất định"} · {r.strategy}: {r.reason_vi}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
