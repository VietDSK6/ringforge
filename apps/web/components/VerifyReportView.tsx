import type { ReactNode } from "react";

import { CounterexampleCard } from "@/components/CounterexampleCard";
import { GroundingLine } from "@/components/GroundingLine";
import { Icon } from "@/components/Icon";
import { VERDICT_TONE, VerdictBadge } from "@/components/VerdictBadge";
import type { Catalog, Check, PolicyPack, VerifyReport } from "@/lib/types";

function title(c: Check): string {
  const unknown = c.status === "UNKNOWN" ? " — không kết luận được trong thời hạn (không coi là đạt)" : "";
  switch (c.code) {
    case "VC-04":
      return `Vi phạm ${c.invariant}${unknown}`;
    case "VC-03":
      return `Luật chết — ${c.rule_id}${unknown}`;
    case "VC-05":
      return `Luật thừa — ${c.redundant} (bị ${c.covered_by} bao trùm)`;
    case "VC-06":
      return `Xung đột miễn trừ — ${c.rule_id} vô hiệu ${c.conflicts_with} ở vùng chồng lấn`;
    case "VC-01":
      return "Luật sai cú pháp/kiểu (VC-01)";
    default:
      return c.code;
  }
}

const EDGE = { pass: "border-l-pass", warn: "border-l-warn", fail: "border-l-fail", unknown: "border-l-unknown" } as const;

/** Báo cáo kiểm chứng (docs/07 mục 3.4): kết luận lớn, thẻ lỗi có phản ví dụ + grounding + luật gây lỗi. */
export function VerifyReportView({
  report,
  pack,
  catalog,
  actions,
}: {
  report: VerifyReport;
  pack: PolicyPack | null;
  catalog: Catalog | null;
  actions?: ReactNode;
}) {
  const source = (id?: string) => pack?.invariants.find((i) => i.id === id)?.source;
  const errors = report.checks.filter((c) => c.severity === "ERROR");
  const warnings = report.checks.filter((c) => c.severity !== "ERROR");
  const tone = VERDICT_TONE[report.verdict];
  return (
    <section aria-labelledby="report-title" className="space-y-4">
      <div className={`panel space-y-4 border-l-4 p-4 sm:p-5 ${EDGE[tone]}`}>
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="space-y-2">
            <h2 id="report-title" className="section-title">
              Kết quả kiểm chứng
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <VerdictBadge verdict={report.verdict} large />
              <span className="num text-sm text-muted">
                {errors.length} lỗi, {warnings.length} cảnh báo
              </span>
            </div>
          </div>
          <dl className="num flex gap-5 text-sm">
            <div>
              <dt className="label">Invariant</dt>
              <dd className="font-semibold">{report.checked.invariants.length}</dd>
            </div>
            <div>
              <dt className="label">Luật</dt>
              <dd className="font-semibold">{report.checked.rules.length}</dd>
            </div>
            <div>
              <dt className="label">Z3</dt>
              <dd className="font-semibold">{report.ms} ms</dd>
            </div>
          </dl>
        </div>

        {errors.length === 0 && report.verdict !== "UNKNOWN" && (
          <p className="text-sm leading-6">
            Với mọi giao dịch trong miền giá trị đã mô hình hóa, bộ luật thỏa tất cả invariant của Policy Pack.
            {warnings.length > 0 && " Có cảnh báo bên dưới (không chặn phê duyệt)."}
          </p>
        )}

        {actions && <div className="border-t border-line pt-4">{actions}</div>}
      </div>

      {[...errors, ...warnings].map((c, i) => {
        const err = c.severity === "ERROR";
        return (
          <article key={i} className={`panel overflow-hidden ${err ? "border-fail-line" : "border-warn-line"}`}>
            <header className={`flex gap-3 border-b px-4 py-3 sm:px-5 ${err ? "border-fail-line bg-fail-soft" : "border-warn-line bg-warn-soft"}`}>
              <span className={`mt-0.5 ${err ? "text-fail" : "text-warn"}`}>
                <Icon name={err ? "x" : "alert"} className="size-5" />
              </span>
              <div className="min-w-0">
                <h3 className="font-semibold leading-6">{title(c)}</h3>
                {c.code === "VC-04" && source(c.invariant) && (
                  <p className="text-[0.8125rem] text-muted">Nguồn: {source(c.invariant)} (giả lập)</p>
                )}
              </div>
            </header>
            <div className="space-y-4 p-4 sm:p-5">
              <p className="max-w-[75ch] text-sm leading-6">{c.message_vi}</p>
              {c.path && <p className="font-mono text-xs text-muted">{c.path}</p>}
              {c.conflicting_conditions_vi && (
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {c.conflicting_conditions_vi.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              )}
              <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                <div data-tour="cex" className="empty:hidden">
                  <CounterexampleCard check={c} catalog={catalog} />
                </div>
                {(c.grounding || (c.blamed_rules && c.blamed_rules.length > 0)) && (
                  <div className="space-y-4">
                    {c.grounding && <GroundingLine g={c.grounding} />}
                    {c.blamed_rules && c.blamed_rules.length > 0 && (
                      <p className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-muted">Luật gây lỗi</span>
                        {c.blamed_rules.map((id) => (
                          <span key={id} className="chip tone-fail font-mono font-semibold">
                            {id}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
