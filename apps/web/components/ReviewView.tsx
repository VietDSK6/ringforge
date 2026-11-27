"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { formatInt, formatVnd } from "@/lib/format";
import type { AuditEvent, ChangeSet, ChangeSetState } from "@/lib/types";

const STATE: Record<ChangeSetState, { label: string; cls: string }> = {
  DRAFT: { label: "Chưa đạt kiểm chứng", cls: "bg-red-50 text-danger ring-red-200 dark:bg-red-950 dark:ring-red-900" },
  VERIFIED: { label: "Chờ duyệt", cls: "bg-violet-50 text-accent ring-violet-200 dark:bg-violet-950 dark:ring-violet-900" },
  APPROVED: { label: "Đã phê duyệt", cls: "bg-emerald-50 text-ok ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-900" },
  REJECTED: { label: "Đã từ chối", cls: "bg-zinc-100 text-muted ring-zinc-300 dark:bg-zinc-900 dark:ring-zinc-700" },
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
  "changeset.create": "Tạo change set",
  "changeset.approve": "Phê duyệt change set",
  "changeset.reject": "Từ chối change set",
  "changeset.approve_blocked": "Phê duyệt bị chặn: kiểm chứng không đạt",
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
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Duyệt thay đổi</h1>
        <p className="text-sm text-muted">
          Mỗi change set mang theo kết quả kiểm chứng, backtest và vùng giao dịch đổi kết quả. Không phê duyệt được change set còn vi phạm
          invariant.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-danger dark:border-red-900 dark:bg-red-950">
          {error}
        </p>
      )}

      {sets !== null && sets.length === 0 && (
        <div className="space-y-2 rounded-2xl border border-dashed border-line p-6 text-sm">
          <p>Chưa có change set nào trong phiên này.</p>
          <p className="text-muted">
            Tạo từ{" "}
            <Link href={`/s/${sid}/studio?demo=1`} className="font-medium text-accent underline">
              Rule Studio
            </Link>{" "}
            sau khi kiểm chứng một luật, hoặc từ{" "}
            <Link href={`/s/${sid}/compare`} className="font-medium text-accent underline">
              So sánh phương án
            </Link>
            .
          </p>
        </div>
      )}

      {sets && sets.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
          <nav aria-label="Danh sách change set">
            <ul className="space-y-2">
              {sets.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/s/${sid}/review?cs=${c.id}`}
                    aria-current={c.id === selected?.id ? "page" : undefined}
                    className={`block rounded-xl border p-3 text-sm ${c.id === selected?.id ? "border-accent bg-surface" : "border-line hover:bg-surface"}`}
                  >
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${STATE[c.state].cls}`}>
                      {STATE[c.state].label}
                    </span>
                    <span className="mt-1 block font-medium">{c.items.map((i) => `${OP_VI[i.op]} ${i.rule_id}`).join(", ")}</span>
                    <span className="block text-xs text-muted">{time(c.created_at)}</span>
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

      <section aria-labelledby={`${uid}-audit`} className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id={`${uid}-audit`} className="text-lg font-semibold">
            Nhật ký kiểm toán
          </h2>
          <label className="inline-flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" checked={showAuto} onChange={(e) => setShowAuto(e.target.checked)} />
            Hiện cả các lần kiểm chứng/backtest tự động
          </label>
        </div>
        <ol className="divide-y divide-line rounded-2xl border border-line bg-surface">
          {visible.map((e) => (
            <li key={e.id} className="grid gap-1 p-3 text-sm sm:grid-cols-[8.5rem_8rem_1fr]">
              <time dateTime={e.created_at} className="tabular-nums text-muted">
                {time(e.created_at)}
              </time>
              <span className={`font-semibold ${e.actor === "ai" ? "text-accent" : ""}`}>{ACTOR_VI[e.actor] ?? e.actor}</span>
              <div>
                <p>{ACTION_VI[e.action] ?? e.action}</p>
                <AuditDetail e={e} />
              </div>
            </li>
          ))}
          {visible.length === 0 && <li className="p-3 text-sm text-muted">Chưa có thao tác nào.</li>}
        </ol>
      </section>
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
      {bits.length > 0 && <p className="text-xs text-muted">{bits.join(" · ")}</p>}
      {ai && (
        <p className="text-xs text-muted">
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
    <div className="rounded-xl bg-background p-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-semibold tabular-nums">{fmt(after)}</dd>
      <dd className="text-xs tabular-nums text-muted">
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
  const open = cs.state === "DRAFT" || cs.state === "VERIFIED";
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
      <header className="flex flex-wrap items-center gap-3">
        <h2 id={`${uid}-title`} className="text-xl font-bold tracking-tight">
          Change set · {cs.items.length} thay đổi
        </h2>
        <span className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 ${STATE[cs.state].cls}`}>{STATE[cs.state].label}</span>
        <span className="text-xs text-muted">Policy Pack {cs.pack_version}</span>
      </header>
      {cs.note && <p className="text-sm">Người đề xuất ghi: “{cs.note}”</p>}

      <ul className="space-y-3">
        {cs.items.map((it) => (
          <li key={`${it.op}-${it.rule_id}`} className="space-y-2 rounded-2xl border border-line bg-surface p-4 text-sm">
            <p className="font-semibold">
              {OP_VI[it.op]} <span className="font-mono">{it.rule_id}</span>
              {it.rule?.provenance?.created_by && it.rule.provenance.created_by !== "human" && (
                <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-900 dark:bg-violet-950 dark:text-violet-200">
                  {it.rule.provenance.created_by === "det_repair" ? "Sửa tất định" : "AI đề xuất"}
                </span>
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

      <section aria-labelledby={`${uid}-verify`} className="space-y-2 rounded-2xl border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 id={`${uid}-verify`} className="font-semibold">
            Kiểm chứng (Z3)
          </h3>
          <VerdictBadge verdict={verify.verdict} />
          <span className="text-xs text-muted">{verify.checked.invariants.length} invariant · {verify.ms} ms</span>
        </div>
        {errors.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-danger">
            {errors.map((c, i) => (
              <li key={i}>{c.message_vi}</li>
            ))}
          </ul>
        )}
        {warns.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-warn">
            {warns.map((c, i) => (
              <li key={i}>{c.message_vi}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby={`${uid}-bt`} className="space-y-3 rounded-2xl border border-line bg-surface p-4">
        <h3 id={`${uid}-bt`} className="font-semibold">
          Backtest trên {bt.days.length} ngày dữ liệu tổng hợp <span className="text-xs font-normal text-muted">(hệ thống tính)</span>
        </h3>
        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Tổn thất ròng L_net" before={bt.before.l_net} after={bt.after.l_net} />
          <Metric label="Lọt gian lận" before={bt.before.fn_loss} after={bt.after.fn_loss} />
          <Metric label="Giao dịch thật bị giữ/chặn" before={bt.before.fp_hold + bt.before.fp_block} after={bt.after.fp_hold + bt.after.fp_block} money={false} />
          <Metric label="Giao dịch thật phải sinh trắc học" before={bt.before.friction_biometric} after={bt.after.friction_biometric} money={false} />
        </dl>
        <p className={`text-sm ${bt.after.valid ? "text-ok" : "font-semibold text-danger"}`}>
          {bt.after.valid
            ? "✅ Không giao dịch nào trong dữ liệu phạm invariant sau thay đổi."
            : `❌ Giao dịch trong dữ liệu phạm invariant sau thay đổi: ${bt.after.compliance_exposure
                .filter((e) => e.count > 0)
                .map((e) => `${e.invariant} ${formatInt(e.count)} (${formatVnd(e.amount_sum)})`)
                .join(" · ")}.`}{" "}
          <span className="text-muted">Δ L_net: {signedVnd(bt.delta.l_net)}</span>
        </p>
      </section>

      <section aria-labelledby={`${uid}-diff`} className="space-y-2 rounded-2xl border border-line bg-surface p-4">
        <h3 id={`${uid}-diff`} className="font-semibold">
          Giao dịch đổi kết quả (semantic diff)
        </h3>
        <p className="text-sm">{diff.message_vi}</p>
        {diff.diffs.length > 0 && (
          <ul className="space-y-1 text-sm">
            {diff.diffs.map((k) => (
              <li key={k.label_vi} className="flex flex-wrap gap-x-2">
                <span className={k.direction === "looser" ? "font-semibold text-danger" : k.direction === "stricter" ? "text-warn" : ""}>
                  {k.direction === "looser" ? "Nới lỏng" : k.direction === "stricter" ? "Chặt hơn" : "Đổi"}: {k.label_vi}
                </span>
                <span className="text-muted">
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

      <section aria-labelledby={`${uid}-decide`} className="space-y-3 rounded-2xl border-2 border-line bg-surface p-4">
        <h3 id={`${uid}-decide`} className="font-semibold">
          Người duyệt
        </h3>
        {open ? (
          <>
            <div>
              <label htmlFor={`${uid}-note`} className="text-sm">
                Ghi chú (bắt buộc khi từ chối)
              </label>
              <textarea
                id={`${uid}-note`}
                rows={2}
                maxLength={1000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="mt-1 w-full rounded-xl border border-zinc-400 bg-background p-3 dark:border-zinc-600"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => decide("approve")}
                disabled={busy || blocked}
                aria-describedby={blocked ? `${uid}-blocked` : undefined}
                className="min-h-12 rounded-xl bg-accent px-6 font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-950"
              >
                Phê duyệt
              </button>
              <button
                type="button"
                onClick={() => decide("reject")}
                disabled={busy}
                className="min-h-12 rounded-xl border border-line px-5 font-semibold hover:bg-background disabled:opacity-50"
              >
                Từ chối
              </button>
            </div>
            {blocked && (
              <p id={`${uid}-blocked`} className="text-sm text-danger">
                Không phê duyệt được: bộ luật sau thay đổi {verify.verdict === "FAIL" ? "còn vi phạm invariant" : "chưa kết luận được"}. Sửa luật
                (ví dụ bằng “Sửa bằng AI” ở Rule Studio) rồi tạo change set mới.
              </p>
            )}
            {message && (
              <p role="alert" className="text-sm text-danger">
                {message}
              </p>
            )}
          </>
        ) : (
          <p role="status" className="text-sm">
            {cs.state === "APPROVED" ? "✅ Đã phê duyệt" : "Đã từ chối"}
            {cs.decided_at ? ` lúc ${time(cs.decided_at)}` : ""}
            {cs.decision_note ? ` — “${cs.decision_note}”` : ""}.
            {cs.state === "APPROVED" && " Các luật trong change set đã chuyển sang trạng thái đang chạy."}
          </p>
        )}
      </section>
    </article>
  );
}
