import { RuleSentence } from "@/components/RuleSentence";
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
  return (
    <article className="space-y-3 rounded-2xl border border-line bg-surface p-4">
      <header className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-xs font-bold text-white dark:bg-white dark:text-zinc-900">
          #{c.rank}
        </span>
        <span className="font-semibold">{STRATEGY_VI[c.strategy]}</span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            c.source === "ai"
              ? "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200"
              : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
          }`}
        >
          {c.source === "ai" ? "AI đề xuất" : "Tất định"}
        </span>
        <span className="ml-auto flex items-center gap-1 text-sm">
          Đã kiểm chứng lại <VerdictBadge verdict={c.verdict} />
        </span>
      </header>

      {c.rules.map((r) => r.render && <RuleSentence key={r.id} render={r.render} compact />)}

      {(c.diff.added_vi.length > 0 || c.diff.removed_vi.length > 0) && (
        <ul className="space-y-1 rounded-xl bg-background p-3 font-mono text-xs" aria-label="Thay đổi điều kiện">
          {c.diff.added_vi.map((t) => (
            <li key={`+${t}`} className="text-ok">
              <span aria-label="thêm">+ </span>
              {t}
            </li>
          ))}
          {c.diff.removed_vi.map((t) => (
            <li key={`-${t}`} className="text-danger line-through">
              <span aria-label="bỏ">− </span>
              {t}
            </li>
          ))}
        </ul>
      )}

      {!c.scope_ok && (
        <p className="text-sm font-medium text-warn">⚠ Bản sửa mở rộng phạm vi ra ngoài luật gốc.</p>
      )}

      <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted">Giữ ý định</dt>
          <dd className="font-semibold tabular-nums">{coverage}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Tổn thất ròng L_net</dt>
          <dd className="font-semibold tabular-nums">{formatVnd(c.l_net)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Δ L_net</dt>
          <dd className="tabular-nums">{signed(c.delta.l_net ?? 0, formatVnd)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Δ ma sát (sinh trắc học)</dt>
          <dd className="tabular-nums">{signed(friction, (x) => `${formatInt(x)} giao dịch`)}</dd>
        </div>
      </dl>

      {(c.rationale_vi || c.intent_lost_vi) && (
        <div className="space-y-1 text-sm">
          {c.rationale_vi && <p>{c.rationale_vi}</p>}
          {c.intent_preserved_vi && <p className="text-ok">Giữ: {c.intent_preserved_vi}</p>}
          {c.intent_lost_vi && <p className="text-muted">Bỏ: {c.intent_lost_vi}</p>}
        </div>
      )}

      <button
        type="button"
        onClick={() => onUse(c)}
        disabled={busy}
        className="min-h-11 rounded-xl bg-accent px-5 font-semibold text-white hover:opacity-90 disabled:opacity-60 dark:text-zinc-950"
      >
        Dùng bản này
      </button>
    </article>
  );
}
