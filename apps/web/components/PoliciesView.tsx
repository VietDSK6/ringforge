"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Callout } from "@/components/Callout";
import { Icon } from "@/components/Icon";
import { ImportExport } from "@/components/ImportExport";
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
  const [version, setVersion] = useState(0); // tăng sau khi nhập bộ luật để tải lại

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
  }, [sid, version]);

  if (error) {
    return (
      <Callout tone="fail" role="alert" title="Không tải được bộ luật">
        <p>{error}</p>
        <Link href="/" className="link">
          Về trang đầu
        </Link>
      </Callout>
    );
  }

  const failed = report?.checks.filter((c) => c.code === "VC-04").map((c) => c.invariant) ?? [];
  const nInv = report?.checked.invariants.length ?? 0;
  const redundant = report?.checks.filter((c) => c.code === "VC-05").map((c) => c.redundant) ?? [];
  const conflicts = report?.checks.filter((c) => c.code === "VC-06").length ?? 0;
  const warnText = [
    redundant.length ? `${redundant.length} luật thừa (${redundant.join(", ")})` : "",
    conflicts ? `${conflicts} xung đột miễn trừ` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Bộ luật</h1>
          <p className="page-lede">Luật đang chạy và ứng viên trong sandbox của bạn.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ImportExport sid={sid} onImported={() => setVersion((v) => v + 1)} />
          <Link href={`/s/${sid}/studio`} className="btn btn-primary">
            <Icon name="plus" />
            Thêm luật bằng lời
          </Link>
        </div>
      </header>

      <div
        role="status"
        className={`panel flex flex-wrap items-center gap-x-4 gap-y-2 border-l-4 px-4 py-3.5 sm:px-5 ${
          !report ? "border-l-line" : report.verdict === "FAIL" ? "border-l-fail" : report.verdict === "UNKNOWN" ? "border-l-unknown" : report.verdict === "PASS" ? "border-l-pass" : "border-l-warn"
        }`}
      >
        {report ? (
          <>
            <VerdictBadge verdict={report.verdict} />
            <span className="text-sm leading-6">
              {failed.length === 0 && report.verdict !== "UNKNOWN"
                ? `Bộ luật đang chạy qua cả ${nInv} invariant của Policy Pack.${warnText ? ` ${warnText}` : ""}`
                : report.verdict === "UNKNOWN"
                  ? "Không kết luận được trong thời hạn — không coi là đạt."
                  : `Vi phạm: ${failed.join(", ")}.`}
            </span>
            <span className="num text-xs text-muted sm:ml-auto">Kiểm bằng Z3 trong {report.ms} ms</span>
          </>
        ) : (
          <span className="flex items-center gap-2 text-sm text-muted">
            <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            Đang kiểm chứng bộ luật…
          </span>
        )}
      </div>

      <div tabIndex={0} role="region" aria-labelledby="rules-caption" className="table-wrap">
        <table className="data-table min-w-[680px]">
          <caption id="rules-caption" className="sr-only">
            Danh sách luật
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-32">ID</th>
              <th scope="col">Luật</th>
              <th scope="col" className="w-28">Loại</th>
              <th scope="col" className="w-32">Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {rules === null && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-muted">
                  Đang tải…
                </td>
              </tr>
            )}
            {rules?.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5 font-mono font-semibold">
                    {r.id}
                    {r.locked && (
                      <span title="Luật pháp lý bị khóa" className="text-muted">
                        <Icon name="lock" className="size-3.5" />
                        <span className="sr-only">Luật pháp lý bị khóa</span>
                      </span>
                    )}
                  </span>
                </td>
                <td className="max-w-[60ch]">
                  <p className="font-medium">{r.name}</p>
                  {r.render && (
                    <div className="mt-0.5 text-muted">
                      <RuleSentence render={r.render} compact />
                    </div>
                  )}
                </td>
                <td className="whitespace-nowrap">
                  <span className={`chip text-xs ${r.kind === "REGULATORY" ? "tone-accent" : "text-muted"}`}>{KIND_VI[r.kind]}</span>
                </td>
                <td className="whitespace-nowrap">
                  <span className="inline-flex items-center gap-2 text-sm">
                    <span
                      aria-hidden
                      className={`size-2 rounded-full ${r.status === "ACTIVE" ? "bg-pass" : r.status === "RETIRED" ? "bg-line-strong" : "bg-warn"}`}
                    />
                    {STATUS_VI[r.status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
