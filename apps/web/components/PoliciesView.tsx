"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { RuleSentence } from "@/components/RuleSentence";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { KIND_VI, STATUS_VI } from "@/lib/format";
import type { Rule, VerifyReport } from "@/lib/types";

/** Workspace: bộ luật của phiên + trạng thái kiểm chứng toàn bộ (docs/07 mục 3.2). */
export function PoliciesView() {
  const { sid } = useParams<{ sid: string }>();
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.rules(sid), api.verify(sid, [])])
      .then(([r, v]) => {
        if (!alive) return;
        setRules(r.rules);
        setReport(v);
      })
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : "Không tải được bộ luật."));
    return () => {
      alive = false;
    };
  }, [sid]);

  if (error) {
    return (
      <div role="alert" className="rounded-2xl border border-line bg-surface p-6">
        <p>{error}</p>
        <Link href="/" className="mt-3 inline-block font-medium text-accent underline">
          Về trang đầu
        </Link>
      </div>
    );
  }

  const failed = report?.checks.filter((c) => c.code === "VC-04").map((c) => c.invariant) ?? [];
  const nInv = report?.checked.invariants.length ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bộ luật</h1>
          <p className="text-sm text-muted">Luật đang chạy và ứng viên trong sandbox của bạn.</p>
        </div>
        <Link
          href={`/s/${sid}/studio`}
          className="inline-flex min-h-11 items-center rounded-xl bg-accent px-5 font-semibold text-white hover:opacity-90 dark:text-zinc-950"
        >
          + Thêm luật bằng lời
        </Link>
      </header>

      <div role="status" className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4">
        {report ? (
          <>
            <VerdictBadge verdict={report.verdict} />
            <span className="text-sm">
              {report.verdict === "PASS"
                ? `Bộ luật đang chạy qua cả ${nInv} invariant của Policy Pack.`
                : `Vi phạm: ${failed.join(", ") || "xem Rule Studio"}.`}
            </span>
            <span className="text-xs text-muted">Kiểm bằng Z3 trong {report.ms} ms</span>
          </>
        ) : (
          <span className="text-sm text-muted">Đang kiểm chứng bộ luật…</span>
        )}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">Danh sách luật</caption>
          <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">ID</th>
              <th scope="col" className="px-4 py-3">Luật</th>
              <th scope="col" className="px-4 py-3">Loại</th>
              <th scope="col" className="px-4 py-3">Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {rules === null && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-muted">
                  Đang tải…
                </td>
              </tr>
            )}
            {rules?.map((r) => (
              <tr key={r.id} className="border-b border-line align-top last:border-0">
                <td className="whitespace-nowrap px-4 py-3 font-mono font-semibold">
                  {r.id} {r.locked && <span title="Luật pháp lý bị khóa">🔒</span>}
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium">{r.name}</p>
                  {r.render && <RuleSentence render={r.render} compact />}
                </td>
                <td className="whitespace-nowrap px-4 py-3">{KIND_VI[r.kind]}</td>
                <td className="whitespace-nowrap px-4 py-3">{STATUS_VI[r.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
