"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { Callout } from "@/components/Callout";
import { Icon } from "@/components/Icon";
import { PageSkeleton } from "@/components/PageSkeleton";
import { SourceTag } from "@/components/SourceTag";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { formatInt, formatVnd } from "@/lib/format";
import type { AuditEvent, ChangeSet, ChangeSetState } from "@/lib/types";

const STATE: Record<ChangeSetState, { label: string; cls: string }> = {
  DRAFT: { label: "Chưa đạt kiểm chứng", cls: "tone-fail" },
  VERIFIED: { label: "Chờ duyệt", cls: "tone-accent" },
  SHADOW: { label: "Chờ duyệt · đã chạy thử", cls: "tone-accent" },
  APPROVED: { label: "Đã phê duyệt", cls: "tone-pass" },
  REJECTED: { label: "Đã từ chối", cls: "tone-unknown" },
};
const OP_VI = { add: "Thêm", replace: "Sửa", retire: "Ngừng" } as const;
const ACTOR_VI: Record<string, string> = {
  "user:proposer": "Người đề xuất",
  "user:approver": "Người duyệt",
  ai: "AI",
  system: "Hệ thống",
};
const ACTION_VI: Record<string, string> = {
  "session.create": "Tạo phiên sandbox",
  "session.reset": "Reset sandbox",
  "rule.compile": "Biên dịch luật từ tiếng Việt",
  "rule.save": "Lưu phiên bản luật",
  "rule.repair_propose": "Đề xuất bản sửa luật",
  "repair.run": "Kiểm chứng lại và xếp hạng bản sửa",
  "verify.run": "Kiểm chứng bộ luật",
  "backtest.run": "Backtest",
  "pack.impact": "Phân tích tác động Policy Pack",
  "pack.apply": "Áp dụng Policy Pack mới",
  "changeset.create": "Tạo đề xuất thay đổi",
  "changeset.approve": "Phê duyệt đề xuất",
  "changeset.reject": "Từ chối đề xuất",
  "changeset.approve_blocked": "Phê duyệt bị chặn: kiểm chứng không đạt",
  "changeset.shadow": "Chạy thử song song trên ngày 7",
  "changeset.summary": "Viết tóm tắt cho người duyệt",
  "ruleset.import": "Nhập bộ luật / Policy Pack",
  "ruleset.export": "Xuất bộ luật",
};
const AUTOMATIC = new Set(["verify.run", "backtest.run"]);

const time = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" });

function signedVnd(n: number) {
  return n === 0 ? "không đổi" : `${n > 0 ? "+" : "−"}${formatVnd(Math.abs(n))}`;
}

/** Duyệt change set: kiểm chứng, backtest, semantic diff, phê duyệt/từ chối, timeline audit (docs/07 mục 3.7). */
export function ReviewView() {
  const { sid } = useParams<{ sid: string }>();
  const search = useSearchParams();
  const uid = useId();
  const [sets, setSets] = useState<ChangeSet[] | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [showAuto, setShowAuto] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [version, setVersion] = useState(0); // tăng sau mỗi quyết định để tải lại

  useEffect(() => {
    let alive = true;
    Promise.all([api.changeSets(sid), api.audit(sid)])
      .then(([cs, au]) => {
        if (!alive) return;
        setSets(cs.change_sets);
        setEvents(au.events);
      })
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu duyệt."));
    return () => {
      alive = false;
    };
  }, [sid, version]);

  const selectedId = search.get("cs") ?? sets?.[0]?.id ?? null;
  const selected = sets?.find((c) => c.id === selectedId) ?? null;
  const visible = showAuto ? events : events.filter((e) => !AUTOMATIC.has(e.action));

  return (
    <div className="space-y-8">
      <header>
        <h1 className="page-title">Duyệt thay đổi</h1>
        <p className="page-lede">
          Mỗi đề xuất thay đổi mang theo kết quả kiểm chứng, backtest và các giao dịch đổi kết quả. Không phê duyệt được đề xuất còn vi
          phạm quy định bắt buộc.
        </p>
      </header>

      {error && (
        <Callout tone="fail" role="alert">
          {error}
        </Callout>
      )}

      {sets === null && !error && <PageSkeleton label="Đang tải đề xuất thay đổi…" rows={3} />}

      {sets !== null && sets.length === 0 && (
        <div className="empty space-y-1 p-5">
          <p className="font-medium text-foreground">Chưa có đề xuất thay đổi nào trong phiên này.</p>
          <p>
            Tạo từ{" "}
            <Link href={`/s/${sid}/studio?demo=1`} className="link">
              Rule Studio
            </Link>{" "}
            sau khi kiểm chứng một luật, hoặc từ{" "}
            <Link href={`/s/${sid}/compare`} className="link">
              So sánh phương án
            </Link>
            .
          </p>
        </div>
      )}

      {sets && sets.length > 0 && (
        <div className="grid items-start gap-6 lg:grid-cols-[17rem_1fr]">
          <nav aria-label="Danh sách đề xuất thay đổi" className="lg:sticky lg:top-12">
            <ul className="space-y-1.5">
              {sets.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/s/${sid}/review?cs=${c.id}`}
                    aria-current={c.id === selected?.id ? "page" : undefined}
                    className={`relative block rounded-lg border p-3 text-sm ${
                      c.id === selected?.id
                        ? "border-line-strong bg-surface font-medium"
                        : "border-transparent text-muted hover:border-line hover:bg-surface hover:text-foreground"
                    }`}
                  >
                    <span className={`chip text-xs font-semibold ${STATE[c.state].cls}`}>{STATE[c.state].label}</span>
                    <span className="mt-1.5 block font-medium text-foreground">{c.items.map((i) => `${OP_VI[i.op]} ${i.rule_id}`).join(", ")}</span>
                    <span className="num block text-xs text-muted">{time(c.created_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          {selected && (
            <ChangeSetDetail
              key={selected.id}
              cs={selected}
              onDecided={() => setVersion((v) => v + 1)}
            />
          )}
        </div>
      )}

      <details aria-labelledby={`${uid}-audit`} className="group panel">
        <summary className="flex min-h-14 cursor-pointer list-none items-center gap-2.5 px-4 sm:px-5 [&::-webkit-details-marker]:hidden">
          <Icon name="chevron" className="size-4 text-muted transition-transform group-open:rotate-90" />
          <h2 id={`${uid}-audit`} className="section-title">
            Nhật ký kiểm toán
          </h2>
          <span className="text-sm text-muted">ai làm gì, lúc nào, dùng model AI nào</span>
        </summary>
        <div className="border-t border-line px-4 py-2 sm:px-5">
          <label className="inline-flex min-h-11 cursor-pointer items-center gap-2.5 text-sm">
            <input type="checkbox" className="size-4" checked={showAuto} onChange={(e) => setShowAuto(e.target.checked)} />
            Hiện cả các lần kiểm chứng/backtest tự động
          </label>
        </div>
        <ol className="divide-y divide-line border-t border-line">
          {visible.map((e) => (
            <li key={e.id} className="grid gap-x-4 gap-y-1 px-4 py-3 text-sm sm:grid-cols-[8.5rem_9.5rem_1fr] sm:px-5">
              <time dateTime={e.created_at} className="num text-muted">
                {time(e.created_at)}
              </time>
              <span className={`font-medium ${e.actor === "ai" ? "text-accent" : ""}`}>
                {ACTOR_VI[e.actor] ?? e.actor}
              </span>
              <div className="min-w-0">
                <p>{ACTION_VI[e.action] ?? e.action}</p>
                <AuditDetail e={e} />
              </div>
            </li>
          ))}
          {visible.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted">Chưa có thao tác nào.</li>}
        </ol>
      </details>
    </div>
  );
}

function AuditDetail({ e }: { e: AuditEvent }) {
  const r = e.ref ?? {};
  const bits: string[] = [];
  if (typeof r.rule_id === "string") bits.push(`luật ${r.rule_id}${r.version ? ` v${r.version}` : ""}`);
  if (Array.isArray(r.items)) bits.push((r.items as string[]).join(", "));
  if (typeof r.verdict === "string") bits.push(`kết luận ${r.verdict}`);
  if (typeof r.version === "string") bits.push(`pack ${r.version}`);
  if (typeof r.note === "string" && r.note) bits.push(`ghi chú: “${r.note}”`);
  if (typeof r.error === "string") bits.push(`lỗi ${r.error}`);
  const ai = e.ai_call;
  return (
    <>
      {bits.length > 0 && <p className="text-xs leading-5 text-muted">{bits.join(" · ")}</p>}
      {ai && (
        <p className="text-xs leading-5 break-words text-muted">
          Model <span className="font-mono">{ai.model}</span> · prompt <span className="font-mono">{ai.prompt_version}</span> · hash{" "}
          <span className="font-mono">{ai.prompt_hash}</span>
          {ai.from_cache ? " · kết quả đã lưu" : ""}
        </p>
      )}
    </>
  );
}

function Metric({ label, before, after, money = true }: { label: string; before: number; after: number; money?: boolean }) {
  const fmt = money ? formatVnd : formatInt;
  const d = after - before;
  return (
    <div className="space-y-0.5 bg-surface p-3">
      <dt className="label">{label}</dt>
      <dd className="num text-lg font-semibold">{fmt(after)}</dd>
      <dd className="num text-xs text-muted">
        {d === 0 ? "không đổi" : `${d > 0 ? "+" : "−"}${fmt(Math.abs(d))}`} so với hiện hành
      </dd>
    </div>
  );
}

function ChangeSetDetail({ cs, onDecided }: { cs: ChangeSet; onDecided: () => void }) {
  const { sid } = useParams<{ sid: string }>();
  const uid = useId();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const verify = cs.summary.verify;
  const bt = cs.summary.backtest;
  const diff = cs.summary.semantic_diff;
  const blocked = verify.verdict === "FAIL" || verify.verdict === "UNKNOWN";
  const open = cs.state === "DRAFT" || cs.state === "VERIFIED" || cs.state === "SHADOW";
  const errors = verify.checks.filter((c) => c.severity === "ERROR");
  const warns = verify.checks.filter((c) => c.severity === "WARN");

  async function decide(decision: "approve" | "reject") {
    setBusy(true);
    setMessage(null);
    try {
      await api.decide(sid, cs.id, decision, note);
      onDecided();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Không ghi được quyết định.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article aria-labelledby={`${uid}-title`} className="min-w-0 space-y-5">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 id={`${uid}-title`} className="page-title text-[1.375rem]">
          Đề xuất · {cs.items.length} thay đổi
        </h2>
        <span className={`chip font-semibold ${STATE[cs.state].cls}`}>{STATE[cs.state].label}</span>
        <span className="font-mono text-xs text-muted">Policy Pack {cs.pack_version}</span>
      </header>
      {cs.note && <p className="text-sm text-muted">Người đề xuất ghi: “{cs.note}”</p>}
      <SummaryBlock cs={cs} onDone={onDecided} />

      <ul className="space-y-3">
        {cs.items.map((it) => (
          <li key={`${it.op}-${it.rule_id}`} className="panel space-y-2 p-4 text-sm leading-6 sm:px-5">
            <p className="flex flex-wrap items-center gap-2 font-semibold">
              {OP_VI[it.op]} <span className="font-mono">{it.rule_id}</span>
              {it.rule?.provenance?.created_by && it.rule.provenance.created_by !== "human" && (
                <SourceTag
                  source={it.rule.provenance.created_by === "det_repair" ? "det" : "ai"}
                  label={it.rule.provenance.created_by === "det_repair" ? "Sửa tự động" : "AI đề xuất"}
                />
              )}
            </p>
            {it.before_vi && (
              <p className="text-muted">
                <span className="font-medium">Trước:</span> <del>{it.before_vi}</del>
              </p>
            )}
            {it.after_vi && (
              <p>
                <span className="font-medium">{it.before_vi ? "Sau:" : "Luật:"}</span> {it.after_vi}
              </p>
            )}
          </li>
        ))}
      </ul>

      <section aria-labelledby={`${uid}-verify`} className="panel space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h3 id={`${uid}-verify`} className="section-title">
            Kiểm chứng (Z3)
          </h3>
          <VerdictBadge verdict={verify.verdict} />
          <span className="num text-xs text-muted">{verify.checked.invariants.length} quy định bắt buộc · {verify.ms} ms</span>
        </div>
        {errors.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-fail">
            {errors.map((c, i) => (
              <li key={i}>{c.message_vi}</li>
            ))}
          </ul>
        )}
        {warns.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-warn">
            {warns.map((c, i) => (
              <li key={i}>{c.message_vi}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby={`${uid}-bt`} className="panel space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id={`${uid}-bt`} className="section-title">
            Backtest trên {bt.days.length} ngày dữ liệu tổng hợp
          </h3>
          <SourceTag source="system" />
        </div>
        <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Tổn thất ròng L_net" before={bt.before.l_net} after={bt.after.l_net} />
          <Metric label="Lọt gian lận" before={bt.before.fn_loss} after={bt.after.fn_loss} />
          <Metric label="Giao dịch thật bị giữ/chặn" before={bt.before.fp_hold + bt.before.fp_block} after={bt.after.fp_hold + bt.after.fp_block} money={false} />
          <Metric label="Giao dịch thật phải sinh trắc học" before={bt.before.friction_biometric} after={bt.after.friction_biometric} money={false} />
        </dl>
        <p className={`text-sm leading-6 ${bt.after.valid ? "text-pass" : "font-semibold text-fail"}`}>
          {bt.after.valid
            ? "Không giao dịch nào trong dữ liệu vi phạm quy định bắt buộc sau thay đổi."
            : `Giao dịch trong dữ liệu vi phạm quy định bắt buộc sau thay đổi: ${bt.after.compliance_exposure
                .filter((e) => e.count > 0)
                .map((e) => `${e.invariant} ${formatInt(e.count)} (${formatVnd(e.amount_sum)})`)
                .join(" · ")}.`}{" "}
          <span className="num font-normal text-muted">Δ L_net: {signedVnd(bt.delta.l_net)}</span>
        </p>
      </section>

      <section aria-labelledby={`${uid}-diff`} className="panel space-y-2 p-4 sm:p-5">
        <h3 id={`${uid}-diff`} className="section-title">
          Giao dịch đổi kết quả
        </h3>
        <p className="text-sm leading-6">{diff.message_vi}</p>
        {diff.diffs.length > 0 && (
          <ul className="space-y-1.5 text-sm leading-6">
            {diff.diffs.map((k) => (
              <li key={k.label_vi} className="flex flex-wrap gap-x-2">
                <span className={k.direction === "looser" ? "font-semibold text-fail" : k.direction === "stricter" ? "text-warn" : ""}>
                  {k.direction === "looser" ? "Nới lỏng" : k.direction === "stricter" ? "Chặt hơn" : "Đổi"}: {k.label_vi}
                </span>
                <span className="num text-muted">
                  · ví dụ {formatVnd(Number(k.counterexample.amount))}
                  {Number(k.counterexample.daily_total_after) > Number(k.counterexample.amount)
                    ? ` (tổng chi trong ngày ${formatVnd(Number(k.counterexample.daily_total_after))})`
                    : ""}
                  {k.data ? ` · ${formatInt(k.data.tx_count)} giao dịch trong dữ liệu` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ShadowSection cs={cs} onDone={onDecided} />

      <section aria-labelledby={`${uid}-decide`} className="panel space-y-4 border-line-strong p-4 sm:p-5">
        <h3 id={`${uid}-decide`} className="section-title">
          Người duyệt
        </h3>
        {open ? (
          <>
            <div>
              <label htmlFor={`${uid}-note`} className="label">
                Ghi chú (bắt buộc khi từ chối)
              </label>
              <textarea
                id={`${uid}-note`}
                rows={2}
                maxLength={1000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="field mt-1 resize-y"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => decide("approve")}
                disabled={busy || blocked}
                aria-describedby={blocked ? `${uid}-blocked` : undefined}
                className="btn btn-primary btn-lg"
              >
                Phê duyệt
              </button>
              <button
                type="button"
                onClick={() => decide("reject")}
                disabled={busy}
                className="btn btn-secondary btn-lg"
              >
                Từ chối
              </button>
            </div>
            {blocked && (
              <Callout tone="fail" id={`${uid}-blocked`}>
                Không phê duyệt được: bộ luật sau thay đổi {verify.verdict === "FAIL" ? "còn vi phạm quy định bắt buộc" : "chưa kết luận được"}. Sửa
                luật (ví dụ bằng “Sửa bằng AI” ở Rule Studio) rồi gửi đề xuất mới.
              </Callout>
            )}
            {message && (
              <Callout tone="fail" role="alert">
                {message}
              </Callout>
            )}
          </>
        ) : (
          <p role="status" className={`text-sm leading-6 ${cs.state === "APPROVED" ? "text-pass" : ""}`}>
            {cs.state === "APPROVED" ? "Đã phê duyệt" : "Đã từ chối"}
            {cs.decided_at ? ` lúc ${time(cs.decided_at)}` : ""}
            {cs.decision_note ? ` — “${cs.decision_note}”` : ""}.
            {cs.state === "APPROVED" && " Các luật trong đề xuất đã chuyển sang trạng thái đang chạy."}
          </p>
        )}
      </section>
    </article>
  );
}

const LABEL_VI: Record<string, string> = { LEGIT: "Thật", APP_VICTIM: "Nạn nhân chuyển cho kẻ gian", ATO: "Chiếm tài khoản", MULE_LAYER: "Mule chuyển tiếp" };
const DEC_SHORT: Record<string, string> = { ALLOW: "Cho qua", MONITOR: "Giám sát", HOLD: "Giữ", BLOCK: "Chặn" };
const AUTH_SHORT: Record<string, string> = { NONE: "", OTP: " · OTP", BIOMETRIC: " · sinh trắc học" };

/** Shadow mô phỏng (FR-A4): bộ luật cũ và mới chạy song song trên ngày 7 — ngày không dùng cho backtest. */
function ShadowSection({ cs, onDone }: { cs: ChangeSet; onDone: () => void }) {
  const { sid } = useParams<{ sid: string }>();
  const uid = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sh = cs.summary.shadow;
  const allowed = cs.state !== "DRAFT" && cs.state !== "REJECTED";

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await api.shadow(sid, cs.id);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không chạy thử được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby={`${uid}-shadow`} className="panel space-y-3 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id={`${uid}-shadow`} className="section-title">
          Chạy thử song song trên ngày 7
        </h3>
        {allowed && (
          <button
            type="button"
            onClick={run}
            disabled={busy}
            className="btn btn-secondary btn-sm"
          >
            {busy ? "Đang chạy thử…" : sh ? "Chạy thử lại" : "Chạy thử trên ngày 7"}
          </button>
        )}
      </div>
      <p className="text-sm text-muted">
        Bộ luật cũ và mới chạy song song trên ngày dữ liệu không dùng cho backtest; không giao dịch nào bị ảnh hưởng thật.
      </p>
      {!allowed && <p className="text-sm text-muted">Chỉ chạy thử được đề xuất đã qua kiểm chứng.</p>}
      {error && (
        <Callout tone="fail" role="alert">
          {error}
        </Callout>
      )}
      {sh && (
        <>
          <p className="num text-sm leading-6">
            {formatInt(sh.changed.tx_count)} / {formatInt(sh.n_tx)} giao dịch đổi kết quả: giữ/chặn thêm{" "}
            <strong>{formatInt(sh.fraud_newly_stopped)} giao dịch gian lận</strong> và{" "}
            <strong className={sh.legit_newly_stopped > 0 ? "text-warn" : undefined}>{formatInt(sh.legit_newly_stopped)} giao dịch thật</strong>
            {sh.auth_lost > 0 && (
              <>
                ; <strong className="text-fail">{formatInt(sh.auth_lost)} giao dịch mất bước xác thực</strong>
              </>
            )}
            . Δ L_net ngày 7: {sh.delta.l_net === 0 ? "không đổi" : `${sh.delta.l_net > 0 ? "+" : "−"}${formatVnd(Math.abs(sh.delta.l_net))}`}{" "}
            <span className="text-xs text-muted">(hệ thống tính)</span>
          </p>
          {sh.samples.length > 0 && (
            <div tabIndex={0} role="region" aria-labelledby={`${uid}-sh-cap`} className="table-wrap shadow-none">
              <table className="data-table min-w-[640px]">
                <caption id={`${uid}-sh-cap`}>
                  Giao dịch đổi kết quả{sh.sample_truncated ? ` (hiện ${sh.samples.length} giao dịch đầu, gian lận trước)` : ""} · nhãn là nhãn
                  dữ liệu tổng hợp
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Giao dịch</th>
                    <th scope="col" className="n">Số tiền</th>
                    <th scope="col">Nhãn</th>
                    <th scope="col">Luật cũ</th>
                    <th scope="col">Luật mới</th>
                  </tr>
                </thead>
                <tbody>
                  {sh.samples.map((t) => (
                    <tr key={t.tx_id}>
                      <th scope="row" className="text-left font-mono text-xs font-normal whitespace-nowrap">
                        {t.tx_id} · {String(t.hour).padStart(2, "0")}:00
                      </th>
                      <td className="n">{formatVnd(t.amount)}</td>
                      <td className={t.label === "LEGIT" ? "" : "font-semibold"}>{LABEL_VI[t.label] ?? t.label}</td>
                      <td className="text-muted">
                        {DEC_SHORT[t.before.decision]}
                        {AUTH_SHORT[t.before.auth]}
                      </td>
                      <td className="font-semibold">
                        {DEC_SHORT[t.after.decision]}
                        {AUTH_SHORT[t.after.auth]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** Tóm tắt cho người duyệt (docs/05 mục 6): AI chỉ viết lời; mọi con số được đối chiếu với số liệu hệ thống. */
function SummaryBlock({ cs, onDone }: { cs: ChangeSet; onDone: () => void }) {
  const { sid } = useParams<{ sid: string }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const s = cs.summary.review_summary;

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await api.summarize(sid, cs.id);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được tóm tắt.");
    } finally {
      setBusy(false);
    }
  }

  const tag =
    s?.source === "ai"
      ? "AI viết · mọi con số đã đối chiếu với số liệu hệ thống"
      : s?.ai === "rejected"
        ? `Mẫu tự động · bản AI bị loại vì có số không có trong dữ liệu (${(s.rejected_numbers ?? []).join(", ")})`
        : "Mẫu tự động · không dùng AI";
  return (
    <section aria-label="Tóm tắt cho người duyệt" className="panel space-y-2 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="section-title">Tóm tắt cho người duyệt</h3>
        <button type="button" onClick={run} disabled={busy} className="btn btn-secondary btn-sm">
          {busy ? "Đang viết tóm tắt…" : s ? "Viết lại" : "Tạo tóm tắt"}
        </button>
      </div>
      {s ? (
        <>
          <p className="max-w-[75ch] text-[0.9375rem] leading-7">{s.summary_vi}</p>
          <SourceTag source={s.source === "ai" ? "ai" : "det"} label={tag} className="rounded-md py-1 text-xs leading-4" />
        </>
      ) : (
        <p className="text-sm text-muted">Tóm tắt 3–5 câu từ kết quả kiểm chứng, backtest và chạy thử; không thay quyết định của bạn.</p>
      )}
      {error && (
        <Callout tone="fail" role="alert">
          {error}
        </Callout>
      )}
    </section>
  );
}
