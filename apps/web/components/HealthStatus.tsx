"use client";

import { useEffect, useState } from "react";

type Health = { status: string; z3_version: string; app_env: string };

type State =
  | { kind: "loading" }
  | { kind: "ok"; health: Health; ms: number }
  | { kind: "error"; message: string };

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
// Máy chủ API có thể đang khởi động lạnh (cold start) nên chờ lâu hơn bình thường.
const TIMEOUT_MS = 60_000;

export function HealthStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), TIMEOUT_MS);
    const started = performance.now();

    fetch(`${API_URL}/health`, { signal: controller.signal, cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Máy chủ trả mã lỗi HTTP ${res.status}`);
        const health = (await res.json()) as Health;
        setState({ kind: "ok", health, ms: Math.round(performance.now() - started) });
      })
      .catch((err: unknown) => {
        if (controller.signal.reason === "unmount") return;
        const message =
          controller.signal.reason === "timeout"
            ? `Quá thời gian chờ (${TIMEOUT_MS / 1000} giây)`
            : err instanceof TypeError
              ? "Không gọi được máy chủ (API chưa chạy, sai địa chỉ hoặc bị chặn CORS)"
              : err instanceof Error
                ? err.message
                : String(err);
        setState({ kind: "error", message });
      })
      .finally(() => clearTimeout(timer));

    return () => {
      clearTimeout(timer);
      controller.abort("unmount");
    };
  }, []);

  return (
    <section
      aria-live="polite"
      className="w-full rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
    >
      {state.kind === "loading" && (
        <StatusLine dotClass="bg-amber-400 animate-pulse" title="Đang kết nối API…" />
      )}
      {state.kind === "ok" && (
        <StatusLine
          dotClass="bg-emerald-500"
          title="API ok"
          detail={`Z3 ${state.health.z3_version} · môi trường ${state.health.app_env} · phản hồi sau ${state.ms.toLocaleString("vi-VN")} ms`}
        />
      )}
      {state.kind === "error" && (
        <StatusLine dotClass="bg-red-500" title="Không kết nối được API" detail={state.message} />
      )}
      <p className="mt-3 break-all font-mono text-xs text-zinc-500">Địa chỉ API: {API_URL}</p>
    </section>
  );
}

function StatusLine({ dotClass, title, detail }: { dotClass: string; title: string; detail?: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${dotClass}`} aria-hidden />
      <div>
        <p className="font-semibold">{title}</p>
        {detail && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{detail}</p>}
      </div>
    </div>
  );
}
