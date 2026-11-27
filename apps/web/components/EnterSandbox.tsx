"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { rememberSession } from "@/lib/session";

/** Nút "Vào sandbox": tạo phiên riêng từ dữ liệu seed (FR-S1) rồi mở màn hình đích (mặc định: Demo 1 kèm hướng dẫn). */
export function EnterSandbox({
  to = "studio",
  query = "?demo=1",
  label = "Vào sandbox",
  variant = "primary",
}: {
  to?: string;
  query?: string;
  label?: string;
  variant?: "primary" | "card";
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enter() {
    setBusy(true);
    setError(null);
    try {
      const { session_id } = await api.createSession();
      rememberSession(session_id);
      // Vào từ trang đầu = muốn xem demo: bật lại hướng dẫn của demo đó dù trước đây đã bỏ qua.
      const demo = new URLSearchParams(query).get("demo");
      if (demo) {
        try {
          localStorage.removeItem(`rf.tour.demo${demo}`);
        } catch {
          /* chế độ riêng tư: hướng dẫn chỉ là tiện ích */
        }
      }
      router.push(`/s/${session_id}/${to}${query}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được phiên sandbox.");
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={enter}
        disabled={busy}
        className={variant === "primary" ? "btn btn-primary btn-lg min-h-12 px-6" : "btn btn-secondary"}
      >
        {busy && <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
        {busy ? "Đang tạo sandbox…" : label}
      </button>
      <p role="status" className={`text-sm text-fail ${error ? "mt-2" : ""}`}>
        {error}
      </p>
    </div>
  );
}
