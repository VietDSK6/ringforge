import { Callout } from "@/components/Callout";
import { CandidateCard } from "@/components/CandidateCard";
import { Icon } from "@/components/Icon";
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
    return <Callout tone="info">{data.message_vi}</Callout>;
  }
  return (
    <section aria-labelledby="repair-title" className="space-y-4">
      <div>
        <h2 id="repair-title" className="section-title">
          Bản sửa đề xuất
        </h2>
        <p className="section-lede">Mọi bản đều đã được kiểm chứng lại và backtest trước khi hiện ở đây.</p>
      </div>
      {LLM_NOTE[data.llm] && <Callout tone="warn">{LLM_NOTE[data.llm]}</Callout>}
      {data.candidates.length === 0 && (
        <div className="empty p-5">Chưa có bản sửa nào qua kiểm chứng. Hãy thử viết lại luật.</div>
      )}
      {data.candidates.map((c) => (
        <CandidateCard key={`${c.source}-${c.rank}`} c={c} onUse={onUse} busy={busy} />
      ))}
      {data.rejected.length > 0 && (
        <details className="group text-sm text-muted">
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 hover:text-foreground [&::-webkit-details-marker]:hidden">
            <Icon name="arrow" className="size-3.5 transition-transform group-open:rotate-90" />
            {data.rejected.length} đề xuất khác bị loại vì không qua kiểm chứng (bấm xem lý do)
          </summary>
          <ul className="mt-1 list-disc space-y-1 pl-10">
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
