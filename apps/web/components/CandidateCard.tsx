import { RuleSentence } from "@/components/RuleSentence";
import { SourceTag } from "@/components/SourceTag";
import { VerdictBadge } from "@/components/VerdictBadge";
import { formatInt, formatVnd } from "@/lib/format";
import type { RepairCandidate } from "@/lib/types";

const STRATEGY_VI: Record<RepairCandidate["strategy"], string> = {
  NARROW_SCOPE: "Thu hẹp phạm vi",
  CHANGE_ACTION: "Đổi hành động",
  SPLIT_RULE: "Tách luật",
  OTHER: "Cách khác",
};

function signed(n: number, fmt: (x: number) => string) {
  if (n === 0) return "không đổi";
  return `${n > 0 ? "+" : "−"}${fmt(Math.abs(n))}`;
}

/** Một bản sửa đã được kiểm chứng lại + backtest (docs/07 mục 3.4). */
export function CandidateCard({ c, onUse, busy }: { c: RepairCandidate; onUse: (c: RepairCandidate) => void; busy: boolean }) {
  const coverage = c.coverage_bp === null ? "—" : `${formatInt(Math.floor(c.coverage_bp / 100))}%`;
  const friction = c.delta.friction_biometric ?? 0;
  const dl = c.delta.l_net ?? 0;
  return (
    <article className="panel overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 sm:px-5">
        <span className="num inline-flex size-7 items-center justify-center rounded-md bg-foreground text-sm font-bold text-background">
          {c.rank}
        </span>
        <h3 className="font-semibold">{STRATEGY_VI[c.strategy]}</h3>
        <SourceTag source={c.source === "ai" ? "ai" : "det"} />
        <span className="ml-auto inline-flex items-center gap-2 text-[0.8125rem] text-muted">
          Đã kiểm chứng lại <VerdictBadge verdict={c.verdict} />
        </span>
      </header>

      <div className="space-y-4 p-4 sm:p-5">
        <div className="space-y-2">{c.rules.map((r) => r.render && <RuleSentence key={r.id} render={r.render} compact />)}</div>

        {(c.diff.added_vi.length > 0 || c.diff.removed_vi.length > 0) && (
          <ul className="space-y-1 overflow-x-auto rounded-md border border-line bg-sunken p-3 font-mono text-[0.8125rem] leading-5" aria-label="Thay đổi điều kiện">
            {c.diff.added_vi.map((t) => (
              <li key={`+${t}`} className="text-pass">
                <span aria-label="thêm">+ </span>
                {t}
              </li>
            ))}
            {c.diff.removed_vi.map((t) => (
              <li key={`-${t}`} className="text-fail line-through">
                <span aria-label="bỏ">− </span>
                {t}
              </li>
            ))}
          </ul>
        )}

        {!c.scope_ok && (
          <p className="text-sm font-medium text-warn">
            Bản sửa mở rộng phạm vi ra ngoài luật gốc.
          </p>
        )}

        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
          {[
            { k: "Giữ ý định", v: coverage, strong: true },
            { k: "Tổn thất ròng L_net", v: formatVnd(c.l_net), strong: true },
            { k: "Δ L_net", v: signed(dl, formatVnd), tone: dl < 0 ? "text-pass" : dl > 0 ? "text-fail" : "" },
            { k: "Δ ma sát (sinh trắc học)", v: signed(friction, (x) => `${formatInt(x)} giao dịch`) },
          ].map((m) => (
            <div key={m.k} className="space-y-0.5 bg-surface p-3">
              <dt className="label">{m.k}</dt>
              <dd className={`num ${m.strong ? "text-base font-semibold" : "text-sm font-medium"} ${m.tone ?? ""}`}>{m.v}</dd>
            </div>
          ))}
        </dl>

        {(c.rationale_vi || c.intent_lost_vi) && (
          <div className="space-y-1 text-sm leading-6">
            {c.rationale_vi && <p>{c.rationale_vi}</p>}
            {c.intent_preserved_vi && <p className="text-pass">Giữ: {c.intent_preserved_vi}</p>}
            {c.intent_lost_vi && <p className="text-muted">Bỏ: {c.intent_lost_vi}</p>}
          </div>
        )}

        <button type="button" onClick={() => onUse(c)} disabled={busy} className="btn btn-primary">
          Dùng bản này
        </button>
      </div>
    </article>
  );
}
