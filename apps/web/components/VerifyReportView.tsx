import type { ReactNode } from "react";

import { CounterexampleCard } from "@/components/CounterexampleCard";
import { GroundingLine } from "@/components/GroundingLine";
import { Icon } from "@/components/Icon";
import { VerdictBadge } from "@/components/VerdictBadge";
import { AUTH_VI, DECISION_VI, formatInt, formatVnd } from "@/lib/format";
import type { Catalog, Check, PolicyPack, VerifyReport } from "@/lib/types";

function title(c: Check): string {
  const unknown = c.status === "UNKNOWN" ? " — không kết luận được trong thời hạn (không coi là đạt)" : "";
  switch (c.code) {
    case "VC-04":
      return `Vi phạm quy định ${c.invariant}${unknown}`;
    case "VC-03":
      return `Luật chết (không bao giờ khớp giao dịch nào) — ${c.rule_id}${unknown}`;
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

/** Mã các luật mà một lỗi/cảnh báo nhắc tới. */
function rulesOf(c: Check): string[] {
  return [...(c.blamed_rules ?? []), c.rule_id, c.redundant, c.covered_by, c.conflicts_with].filter((x): x is string => !!x);
}

/** Câu tóm tắt bằng lời thường, ghép hoàn toàn từ số liệu hệ thống tính (không dùng AI). */
function Summary({
  report,
  errors,
  otherWarnings,
  pack,
}: {
  report: VerifyReport;
  errors: Check[];
  otherWarnings: number;
  pack: PolicyPack | null;
}) {
  const nInv = report.checked.invariants.length;
  if (report.verdict === "UNKNOWN") {
    return <p className="text-[0.9375rem] leading-7">Z3 chưa kết luận được trong thời hạn, nên bộ luật chưa được coi là đạt.</p>;
  }
  if (errors.length === 0) {
    return (
      <p className="text-[0.9375rem] leading-7">
        Với mọi giao dịch có thể có, bộ luật đáp ứng cả {nInv} quy định bắt buộc của Policy Pack.
        {otherWarnings > 0 && ` ${otherWarnings} cảnh báo còn lại thuộc bộ luật đang chạy, không do luật này gây ra và không chặn phê duyệt.`}
      </p>
    );
  }
  const violations = errors.filter((c) => c.code === "VC-04");
  const first = violations.find((c) => c.counterexample) ?? errors[0];
  const tx = first.counterexample;
  const g = first.grounding;
  const sources = [...new Set(violations.map((c) => pack?.invariants.find((i) => i.id === c.invariant)?.source).filter(Boolean))];
  return (
    <div className="space-y-1 text-[0.9375rem] leading-7">
      <p>
        {violations.length > 0 ? (
          <>
            Bộ luật <strong>vi phạm {violations.length} quy định bắt buộc</strong>
            {sources.length > 0 && ` (${sources.join(", ")} — giả lập)`}.
          </>
        ) : (
          <>
            Bộ luật có <strong>{errors.length} lỗi</strong> cần sửa trước khi duyệt.
          </>
        )}
      </p>
      {tx && first.outcome && (
        <p>
          Ví dụ: một giao dịch <strong className="num">{formatVnd(Number(tx.amount))}</strong> vẫn được{" "}
          <strong>
            {DECISION_VI[first.outcome.decision].toLowerCase()}, {AUTH_VI[first.outcome.auth]}
          </strong>
          .
        </p>
      )}
      {g &&
        (g.tx_count > 0 ? (
          <p>
            Trong {g.days.length} ngày dữ liệu tổng hợp có{" "}
            <strong className="num">
              {formatInt(g.tx_count)} giao dịch như vậy, tổng {formatVnd(g.amount_sum)}
            </strong>
            .
          </p>
        ) : (
          <p>
            Trong {g.days.length} ngày dữ liệu chưa có giao dịch nào như vậy: backtest sẽ không thấy lỗi này, chỉ kiểm chứng hình thức bắt
            được.
          </p>
        ))}
    </div>
  );
}

/**
 * Báo cáo kiểm chứng (docs/07 mục 3.4): kết luận + câu tóm tắt, thẻ lỗi có phản ví dụ + grounding + luật gây lỗi.
 * focusRuleIds: luật đang được kiểm (vd. luật vừa viết) — cảnh báo không nhắc tới luật nào trong số này được gom vào mục thu gọn.
 */
export function VerifyReportView({
  report,
  pack,
  catalog,
  actions,
  focusRuleIds,
}: {
  report: VerifyReport;
  pack: PolicyPack | null;
  catalog: Catalog | null;
  actions?: ReactNode;
  focusRuleIds?: string[];
}) {
  const source = (id?: string) => pack?.invariants.find((i) => i.id === id)?.source;
  const errors = report.checks.filter((c) => c.severity === "ERROR");
  const warnings = report.checks.filter((c) => c.severity !== "ERROR");
  const related = (c: Check) => !focusRuleIds?.length || rulesOf(c).some((id) => focusRuleIds.includes(id));
  const ownWarnings = warnings.filter(related);
  const otherWarnings = warnings.filter((c) => !related(c));

  return (
    <section aria-labelledby="report-title" className="space-y-4">
      <div className="panel space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="space-y-2">
            <h2 id="report-title" className="section-title">
              Kết quả kiểm chứng
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <VerdictBadge verdict={report.verdict} large />
              <span className="num text-sm text-muted">
                {errors.length} lỗi, {ownWarnings.length} cảnh báo
              </span>
            </div>
          </div>
          <dl className="num flex gap-5 text-sm">
            <div>
              <dt className="label">Quy định</dt>
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

        <div className="max-w-[72ch]">
          <Summary report={report} errors={errors} otherWarnings={otherWarnings.length} pack={pack} />
        </div>

        {actions && <div className="border-t border-line pt-4">{actions}</div>}
      </div>

      {[...errors, ...ownWarnings].map((c, i) => (
        <CheckCard key={i} c={c} catalog={catalog} requirement={pack?.invariants_vi?.[c.invariant ?? ""]} source={source(c.invariant)} />
      ))}

      {otherWarnings.length > 0 && (
        <details className="group panel text-sm">
          <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 px-4 sm:px-5 [&::-webkit-details-marker]:hidden">
            <Icon name="chevron" className="size-3.5 text-muted transition-transform group-open:rotate-90" />
            <span>
              {otherWarnings.length} cảnh báo khác của bộ luật đang chạy{" "}
              <span className="text-muted">— không liên quan luật đang kiểm, không chặn phê duyệt</span>
            </span>
          </summary>
          <ul className="space-y-2 border-t border-line px-4 py-3 sm:px-5">
            {otherWarnings.map((c, i) => (
              <li key={i} className="leading-6">
                <span className="font-medium text-warn">{title(c)}.</span> {c.message_vi}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function CheckCard({ c, catalog, requirement, source }: { c: Check; catalog: Catalog | null; requirement?: string; source?: string }) {
  const err = c.severity === "ERROR";
  return (
    <article className={`panel overflow-hidden ${err ? "border-fail-line" : "border-warn-line"}`}>
      <header className={`space-y-0.5 border-b px-4 py-3 sm:px-5 ${err ? "border-fail-line bg-fail-soft" : "border-warn-line bg-warn-soft"}`}>
        <h3 className={`font-semibold leading-6 ${err ? "text-fail" : "text-warn"}`}>{title(c)}</h3>
        {c.code === "VC-04" && requirement && <p className="max-w-[80ch] text-sm leading-6">Quy định: {requirement}</p>}
        {c.code === "VC-04" && source && <p className="text-[0.8125rem] text-muted">Nguồn: {source} (giả lập)</p>}
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
}
