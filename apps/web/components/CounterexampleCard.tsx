import { Icon } from "@/components/Icon";
import { AUTH_VI, DECISION_VI, formatFieldValue, formatVnd } from "@/lib/format";
import type { Catalog, Outcome, Transaction } from "@/lib/types";

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

/** Phản ví dụ trình bày như một giao dịch trong app — biên lai: số tiền to, chi tiết, kết quả của bộ luật (docs/07 mục 3.4). */
export function CounterexampleCard({
  check,
  catalog,
  title = "Giao dịch phản ví dụ (do hệ thống tìm)",
}: {
  check: { counterexample?: Transaction; outcome?: Outcome; outcomes?: { before: Outcome; after: Outcome } };
  catalog: Catalog | null;
  title?: string;
}) {
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
  const daily = Number(tx.daily_total_after) > Number(tx.amount);

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-line bg-sunken px-4 py-2 text-[0.8125rem] text-muted">
        <span className="font-medium">{title}</span>
        <span className="num">{show("hour")}</span>
      </div>

      <div className="px-4 pt-4 pb-3">
        <p className="text-sm text-muted">{show("channel")}</p>
        <p className="num mt-0.5 text-4xl leading-tight font-bold tracking-tight sm:text-[2.75rem]">{formatVnd(Number(tx.amount))}</p>
        {daily && (
          <p className="num mt-1 text-lg font-semibold">
            Tổng chi trong ngày (gồm giao dịch này): {formatVnd(Number(tx.daily_total_after))}
          </p>
        )}
      </div>

      <dl className="mx-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 border-t border-dashed border-line-strong py-3 text-sm">
        <dt className="text-muted">Tài khoản gửi</dt>
        <dd className="num text-right font-medium">{show("sender_account_age_days")}</dd>
        <dt className="text-muted">Người nhận</dt>
        <dd className="text-right font-medium">{receiver}</dd>
      </dl>

      {check.outcome && (
        <div className="mx-4 border-t border-dashed border-line-strong py-3 text-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <span className="text-muted">Bộ luật cho kết quả</span>
            <span className="font-semibold text-fail">
              {DECISION_VI[check.outcome.decision]} · {AUTH_VI[check.outcome.auth]}
            </span>
          </div>
          <p className="mt-1 text-right text-[0.8125rem] font-medium text-fail">✕ Kết quả này trái quy định</p>
        </div>
      )}
      {check.outcomes && (
        <dl className="mx-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 border-t border-dashed border-line-strong py-3 text-sm">
          <dt className="text-muted">Trước thay đổi</dt>
          <dd className="text-right">
            {DECISION_VI[check.outcomes.before.decision]} · {AUTH_VI[check.outcomes.before.auth]}
          </dd>
          <dt className="text-muted">Sau thay đổi</dt>
          <dd className="text-right font-semibold">
            {DECISION_VI[check.outcomes.after.decision]} · {AUTH_VI[check.outcomes.after.auth]}
          </dd>
        </dl>
      )}

      {rest.length > 0 && (
        <details className="group border-t border-line text-sm">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-4 text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
            <Icon name="chevron" className="size-3.5 transition-transform group-open:rotate-90" />
            Các trường còn lại của giao dịch
          </summary>
          <dl className="grid grid-cols-1 gap-x-6 px-4 pb-3 sm:grid-cols-2">
            {rest.map((k) => (
              <div key={k} className="flex justify-between gap-3 border-b border-line py-1.5 last:border-0">
                <dt className="text-muted">{field(k)?.label_vi ?? k}</dt>
                <dd className="num text-right">{show(k)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
