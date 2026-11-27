"use client";

import { Callout } from "@/components/Callout";
import { useHealth } from "@/components/useHealth";

/** Chế độ dự phòng khi LLM không khả dụng (FR-S5, docs/07 mục 5). Kiểm chứng, backtest, sửa tất định không cần AI. */
export function AiStatusBanner() {
  const state = useHealth();
  if (state.kind !== "ok" || state.health.llm !== "fallback") return null;
  const cached = state.health.ai_cache_entries ?? 0;
  return (
    <Callout tone="warn" role="status" title="AI tạm thời không khả dụng">
      <p>
        {cached > 0 ? `${cached} câu mẫu dùng kết quả đã lưu (có nhãn)` : "Chưa có kết quả AI đã lưu cho câu mẫu"}. Bạn vẫn viết luật bằng
        JSON, kiểm chứng, sửa tất định, backtest và duyệt như bình thường.
      </p>
    </Callout>
  );
}
