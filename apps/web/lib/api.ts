// Client gọi API RingForge. Lỗi API trả về dạng {error_code, message_vi} → ApiError.
import type { Assumptions, AuditEvent, BacktestResponse, Catalog, ChangeSet, CompileResult, PackImpact, PatchOp, PolicyPack, RepairResponse, Rule, VerifyReport } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Không gọi được máy chủ (có thể đang khởi động). Thử lại sau vài giây.");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = body?.message_vi ?? `Máy chủ trả mã lỗi HTTP ${res.status}.`;
    throw new ApiError(res.status, body?.error_code ?? "HTTP_ERROR", msg, body?.details);
  }
  return body as T;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  createSession: () => post<{ session_id: string; pack_version: string; rules: number }>("/sessions", {}),
  resetSession: (sid: string) => post<{ reset: boolean }>(`/sessions/${sid}/reset`, {}),
  rules: (sid: string) => request<{ pack_version: string; rules: Rule[] }>(`/sessions/${sid}/rules`),
  pack: (sid: string) => request<PolicyPack>(`/sessions/${sid}/pack`),
  catalog: () => request<Catalog>("/catalog"),
  compile: (sid: string, text: string) => post<CompileResult>(`/sessions/${sid}/compile`, { text }),
  verify: (sid: string, rules: unknown[]) => post<VerifyReport>(`/sessions/${sid}/verify`, { rules }),
  repair: (sid: string, rule: unknown, useAi = true) =>
    post<RepairResponse>(`/sessions/${sid}/repair`, { rule, use_ai: useAi }),
  packImpact: (sid: string, patch: PatchOp[]) => post<PackImpact>(`/sessions/${sid}/pack/impact`, { patch }),
  packApply: (sid: string, patch: PatchOp[]) =>
    post<{ pack: PolicyPack; previous_version: string }>(`/sessions/${sid}/pack/apply`, { patch }),
  backtest: (sid: string, variants: unknown[], assumptions: Assumptions, signal?: AbortSignal) =>
    request<BacktestResponse>(`/sessions/${sid}/backtest`, {
      method: "POST",
      body: JSON.stringify({ variants, assumptions }),
      signal,
    }),
  createChangeSet: (sid: string, items: unknown[], note = "") => post<ChangeSet>(`/sessions/${sid}/change-sets`, { items, note }),
  changeSets: (sid: string) => request<{ change_sets: ChangeSet[] }>(`/sessions/${sid}/change-sets`),
  decide: (sid: string, id: string, decision: "approve" | "reject", note: string) =>
    post<ChangeSet>(`/sessions/${sid}/change-sets/${id}/decision`, { decision, note, role: "approver" }),
  audit: (sid: string) => request<{ events: AuditEvent[] }>(`/sessions/${sid}/audit`),
  exportRuleset: (sid: string) => request<Record<string, unknown>>(`/sessions/${sid}/export`),
  importRuleset: (sid: string, body: Record<string, unknown>) =>
    post<{ imported: { rules: number; policy_pack: string | null; mode: string }; rules_total: number; verify: VerifyReport }>(
      `/sessions/${sid}/import`,
      body,
    ),
  saveRule: (sid: string, rule: Rule | Record<string, unknown>) =>
    request<{ saved: boolean; rule?: Rule }>(`/sessions/${sid}/rules/${String(rule.id)}`, {
      method: "PUT",
      body: JSON.stringify(rule),
    }),
};
