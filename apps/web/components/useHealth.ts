"use client";

import { useEffect, useState } from "react";

import { API_URL } from "@/lib/api";

export type Health = { status: string; z3_version?: string; app_env?: string; llm?: string; ai_cache_entries?: number };
export type HealthState = { kind: "loading" } | { kind: "ok"; health: Health } | { kind: "error" };

// Một lần gọi /health cho cả trang (thanh trạng thái + banner dự phòng AI dùng chung).
let pending: Promise<Health> | null = null;

function load(): Promise<Health> {
  pending ??= fetch(`${API_URL}/health`, { cache: "no-store" }).then((r) => {
    if (!r.ok) throw new Error(String(r.status));
    return r.json() as Promise<Health>;
  });
  pending.catch(() => {
    pending = null; // lần sau thử lại
  });
  return pending;
}

export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ kind: "loading" });
  useEffect(() => {
    let alive = true;
    load()
      .then((health) => alive && setState({ kind: "ok", health }))
      .catch(() => alive && setState({ kind: "error" }));
    return () => {
      alive = false;
    };
  }, []);
  return state;
}
