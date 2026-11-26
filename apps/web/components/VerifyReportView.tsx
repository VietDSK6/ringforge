import { CounterexampleCard } from "@/components/CounterexampleCard";
import { VerdictBadge } from "@/components/VerdictBadge";
import type { Catalog, PolicyPack, VerifyReport } from "@/lib/types";

/** Báo cáo kiểm chứng (bản cơ bản; màn hình đầy đủ + grounding + sửa bằng AI ở T3.5). */
export function VerifyReportView({ report, pack, catalog }: { report: VerifyReport; pack: PolicyPack | null; catalog: Catalog | null }) {
  const source = (id?: string) => pack?.invariants.find((i) => i.id === id)?.source;
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

      {report.verdict === "PASS" && (
        <p className="rounded-xl border border-line bg-surface p-4 text-sm">
          Với mọi giao dịch trong miền giá trị đã mô hình hóa, bộ luật thỏa tất cả invariant của Policy Pack.
        </p>
      )}

      {report.checks.map((c, i) => (
        <article key={i} className="space-y-3 rounded-2xl border border-line bg-surface p-4">
          <header>
            <h3 className="font-semibold">
              {c.code === "VC-04" && `Vi phạm ${c.invariant}`}
              {c.code === "VC-03" && `Luật chết — ${c.rule_id}`}
              {c.code === "VC-01" && "Luật sai cú pháp/kiểu (VC-01)"}
              {c.status === "UNKNOWN" && " — không kết luận được"}
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
          <CounterexampleCard check={c} catalog={catalog} />
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
