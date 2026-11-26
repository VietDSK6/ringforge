import { AUTH_VI, DECISION_VI, formatFieldValue, formatVnd } from "@/lib/format";
import type { Catalog, Check } from "@/lib/types";

// Các trường đã hiển thị ở phần chính của thẻ.
const MAIN = new Set([
  "amount",
  "daily_total_after",
  "channel",
  "hour",
  "sender_account_age_days",
  "receiver_is_familiar",
  "receiver_is_verified_merchant",
]);

/** Phản ví dụ trình bày như một giao dịch trong app (docs/07 mục 3.4). */
export function CounterexampleCard({ check, catalog }: { check: Check; catalog: Catalog | null }) {
  const tx = check.counterexample;
  if (!tx) return null;
  const field = (name: string) => catalog?.fields.find((f) => f.name === name);
  const show = (name: string) => formatFieldValue(field(name), tx[name]);
  const receiver = tx.receiver_is_verified_merchant
    ? "merchant đã xác minh"
    : tx.receiver_is_familiar
      ? "người nhận quen"
      : "người nhận chưa quen";
  const rest = Object.keys(tx).filter((k) => !MAIN.has(k));

  return (
    <div className="rounded-2xl border border-line bg-background p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">Giao dịch phản ví dụ (do hệ thống tìm)</p>
      <p className="mt-1 text-3xl font-bold tabular-nums">{formatVnd(Number(tx.amount))}</p>
      {Number(tx.daily_total_after) > Number(tx.amount) && (
        <p className="mt-1 text-lg font-semibold tabular-nums">
          Tổng chi trong ngày (gồm giao dịch này): {formatVnd(Number(tx.daily_total_after))}
        </p>
      )}
      <p className="mt-1 text-sm text-muted">
        {show("channel")} · {show("hour")} · tài khoản gửi {show("sender_account_age_days")} · {receiver}
      </p>
      {check.outcome && (
        <p className="mt-3 text-sm">
          Bộ luật cho kết quả:{" "}
          <span className="font-semibold text-danger line-through decoration-2">
            {DECISION_VI[check.outcome.decision]} · {AUTH_VI[check.outcome.auth]}
          </span>
        </p>
      )}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Các trường còn lại của giao dịch</summary>
        <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
          {rest.map((k) => (
            <div key={k} className="flex justify-between gap-3 border-b border-line py-1">
              <dt className="text-muted">{field(k)?.label_vi ?? k}</dt>
              <dd className="text-right tabular-nums">{show(k)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
