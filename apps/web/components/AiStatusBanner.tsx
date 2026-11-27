"use client";

import { useEffect, useState } from "react";

import { API_URL } from "@/lib/api";

/** Chế độ dự phòng khi LLM không khả dụng (FR-S5, docs/07 mục 5). Kiểm chứng, backtest, sửa tất định không cần AI. */
export function AiStatusBanner() {
  const [cached, setCached] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}/health`, { cache: "no-store" })
      .then((r) => r.json())
      .then((h: { llm?: string; ai_cache_entries?: number }) => {
        if (alive && h.llm === "fallback") setCached(h.ai_cache_entries ?? 0);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (cached === null) return null;
  return (
    <p role="status" className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
      AI tạm thời không khả dụng —{" "}
      {cached > 0 ? `${cached} câu mẫu dùng kết quả đã lưu (có nhãn)` : "chưa có kết quả AI đã lưu cho câu mẫu"}. Bạn vẫn viết luật bằng JSON,
      kiểm chứng, sửa tất định, backtest và duyệt như bình thường.
    </p>
  );
}
