"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { rememberSession } from "@/lib/session";

/** Nút "Vào sandbox": tạo phiên riêng từ dữ liệu seed (FR-S1) rồi mở màn hình đích. */
export function EnterSandbox({
  to = "studio",
  query = "",
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
        className={
          variant === "primary"
            ? "min-h-12 rounded-xl bg-accent px-6 text-base font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-60 dark:text-zinc-950"
            : "min-h-10 rounded-lg border border-line px-4 text-sm font-medium hover:bg-background disabled:opacity-60"
        }
      >
        {busy ? "Đang tạo sandbox…" : label}
      </button>
      <p role="status" className="mt-2 text-sm text-danger">
        {error}
      </p>
    </div>
  );
}
