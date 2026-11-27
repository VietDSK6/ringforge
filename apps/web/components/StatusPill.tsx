"use client";

import { useHealth } from "@/components/useHealth";

/** Trạng thái API + AI trên thanh đầu trang (đọc /health). */
export function StatusPill() {
  const state = useHealth();
  const api =
    state.kind === "loading"
      ? { dot: "bg-warn animate-pulse", text: "Đang kết nối máy chủ…" }
      : state.kind === "error"
        ? { dot: "bg-fail", text: "Mất kết nối máy chủ" }
        : { dot: "bg-pass", text: "Máy chủ sẵn sàng" };
  const llm = state.kind === "ok" ? state.health.llm : undefined;
  const ai =
    llm === undefined
      ? null
      : llm === "fallback"
        ? { dot: "bg-warn", text: "AI dự phòng" }
        : { dot: "bg-pass", text: "AI sẵn sàng" };

  return (
    <p role="status" aria-live="polite" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.8125rem] text-muted">
      <span className="inline-flex items-center gap-2">
        <span className={`size-2 rounded-full ${api.dot}`} aria-hidden />
        {api.text}
      </span>
      {ai && (
        <span className="inline-flex items-center gap-2">
          <span className={`size-2 rounded-full ${ai.dot}`} aria-hidden />
          {ai.text}
        </span>
      )}
    </p>
  );
}
