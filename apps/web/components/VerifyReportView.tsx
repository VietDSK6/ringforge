import type { ReactNode } from "react";

import { CounterexampleCard } from "@/components/CounterexampleCard";
import { GroundingLine } from "@/components/GroundingLine";
import { VerdictBadge } from "@/components/VerdictBadge";
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

/** Báo cáo kiểm chứng (docs/07 mục 3.4): badge lớn, thẻ lỗi có phản ví dụ + grounding + luật gây lỗi. */
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
  return (
    <section aria-labelledby="report-title" className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="report-title" className="text-lg font-semibold">
          Kết quả kiểm chứng
        </h2>
        <VerdictBadge verdict={report.verdict} large />
        <span className="text-xs text-muted">
          Z3 · {report.checked.invariants.length} invariant · {report.checked.rules.length} luật · {report.ms} ms
        </span>
      </div>

      {errors.length === 0 && report.verdict !== "UNKNOWN" && (
        <p className="rounded-xl border border-line bg-surface p-4 text-sm">
          Với mọi giao dịch trong miền giá trị đã mô hình hóa, bộ luật thỏa tất cả invariant của Policy Pack.
          {warnings.length > 0 && " Có cảnh báo bên dưới (không chặn phê duyệt)."}
        </p>
      )}

      {actions}

      {[...errors, ...warnings].map((c, i) => (
        <article
          key={i}
          className={`space-y-3 rounded-2xl border bg-surface p-4 ${
            c.severity === "ERROR" ? "border-red-300 dark:border-red-900" : "border-amber-300 dark:border-amber-800"
          }`}
        >
          <header>
            <h3 className="font-semibold">
              <span aria-hidden>{c.severity === "ERROR" ? "❌ " : "⚠️ "}</span>
              {title(c)}
            </h3>
            {c.code === "VC-04" && source(c.invariant) && (
              <p className="text-xs text-muted">Nguồn: {source(c.invariant)} (giả lập)</p>
            )}
          </header>
          <p className="text-sm">{c.message_vi}</p>
          {c.path && <p className="font-mono text-xs text-muted">{c.path}</p>}
          {c.conflicting_conditions_vi && (
            <ul className="list-disc pl-5 text-sm">
              {c.conflicting_conditions_vi.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          )}
          <div data-tour="cex">
            <CounterexampleCard check={c} catalog={catalog} />
          </div>
          {c.grounding && <GroundingLine g={c.grounding} />}
          {c.blamed_rules && c.blamed_rules.length > 0 && (
            <p className="text-sm">
              Luật gây lỗi: <span className="font-mono font-semibold text-danger">{c.blamed_rules.join(", ")}</span>
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
