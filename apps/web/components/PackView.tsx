"use client";

import { useParams, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { CounterexampleCard } from "@/components/CounterexampleCard";
import { GroundingLine } from "@/components/GroundingLine";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";
import { RuleSentence } from "@/components/RuleSentence";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { AUTH_VI, DECISION_VI, formatInt, formatVnd } from "@/lib/format";
import type { Catalog, ImpactRule, PackImpact, PatchOp, PolicyPack, Rule } from "@/lib/types";

const DEMO2 = { param: "biometric_per_tx_threshold", value: 5_000_000 };
const DEMO_SOURCE = "Kịch bản giả lập Demo 2 — không phải quy định thật";

const fmtParam = (value: number, unit: string) =>
  unit === "VND" ? formatVnd(value) : `${formatInt(value)}${unit ? ` ${unit === "s" ? "giây" : unit}` : ""}`;

const TOUR: TourStep[] = [
  { target: "param", text: "Ngưỡng sinh trắc học/lần đã hạ sẵn từ 10 xuống 5 triệu." },
  { target: "analyze", text: "Bấm Phân tích tác động: kiểm chứng lại toàn bộ bộ luật.", advanceOn: "click" },
  { target: "incompatible", text: "LG-07 viết cứng 10.000.000 nên không còn tương thích, kèm nhân chứng.", waiting: "Đang phân tích…" },
  { target: "friction", text: "Ma sát: thêm bao nhiêu giao dịch thật phải sinh trắc học." },
  { target: "fix", text: "Lưu bản sửa tham chiếu tham số; đã kiểm chứng lại.", advanceOn: "click" },
];

const digits = (s: string) => s.replace(/\D/g, "");

function withoutRender(rule: Rule): Omit<Rule, "render"> {
  const { render: _render, ...rest } = rule;
  void _render;
  return rest;
}

/** Policy Pack + phân tích tác động khi đổi tham số (docs/07 mục 3.6 — Demo 2). */
export function PackView() {
  const { sid } = useParams<{ sid: string }>();
  const search = useSearchParams();
  const isDemo = search.get("demo") === "2";
  const [pack, setPack] = useState<PolicyPack | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [impact, setImpact] = useState<PackImpact | null>(null);
  const [patch, setPatch] = useState<PatchOp[]>([]);
  const [busy, setBusy] = useState<"analyze" | "apply" | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const [saved, setSaved] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formId = useId();

  useEffect(() => {
    let alive = true;
    api
      .pack(sid)
      .then((p) => {
        if (!alive) return;
        setPack(p);
        const init = Object.fromEntries(Object.entries(p.params).map(([k, v]) => [k, formatInt(v.value)]));
        if (isDemo && p.params[DEMO2.param]?.value !== DEMO2.value) init[DEMO2.param] = formatInt(DEMO2.value);
        setDraft(init);
      })
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : "Không tải được Policy Pack."));
    api.catalog().then((c) => alive && setCatalog(c)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [sid, isDemo]);

  function buildPatch(p: PolicyPack): PatchOp[] {
    return Object.entries(p.params).flatMap(([name, param]) => {
      const raw = digits(draft[name] ?? "");
      if (!raw || Number(raw) === param.value) return [];
      const op: PatchOp = { op: "set_param", param: name, value: Number(raw) };
      return [isDemo ? { ...op, source: DEMO_SOURCE } : op];
    });
  }

  const pending = pack ? buildPatch(pack) : [];

  async function analyze(e: FormEvent) {
    e.preventDefault();
    if (!pack || pending.length === 0) return;
    setBusy("analyze");
    setError(null);
    setApplied(null);
    setSaved({});
    try {
      const res = await api.packImpact(sid, pending);
      setImpact(res);
      setPatch(pending);
      requestAnimationFrame(() => resultsRef.current?.focus());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Phân tích tác động thất bại.");
    } finally {
      setBusy(null);
    }
  }

  async function applyPack(): Promise<boolean> {
    if (applied) return true;
    setBusy("apply");
    setError(null);
    try {
      const res = await api.packApply(sid, patch);
      setApplied(res.pack.version);
      const fresh = await api.pack(sid);
      setPack(fresh);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Áp dụng Policy Pack thất bại.");
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function saveFix(r: ImpactRule) {
    if (!r.fix?.rule) return;
    if (!(await applyPack())) return;
    try {
      const res = await api.saveRule(sid, withoutRender(r.fix.rule));
      if (res.saved && res.rule) setSaved((s) => ({ ...s, [r.id]: res.rule!.version }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được bản sửa.");
    }
  }

  function onDraft(name: string, value: string) {
    setDraft((d) => ({ ...d, [name]: value }));
    if (impact && !applied) setImpact(null); // kết quả cũ không còn khớp giá trị đang nhập
  }

  if (error && !pack) {
    return (
      <p role="alert" className="rounded-2xl border border-line bg-surface p-6">
        {error}
      </p>
    );
  }
  if (!pack) return <p className="text-muted">Đang tải Policy Pack…</p>;

  const byCat = (c: ImpactRule["category"]) => impact?.rules.filter((r) => r.category === c) ?? [];
  const nextVersion = impact?.pack_after.version;

  return (
    <div className="space-y-8">
      <GuidedTour id="demo2" steps={TOUR} enabled={isDemo} />
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Policy Pack</h1>
        <p className="text-sm text-muted">
          {pack.id} · phiên bản <span className="font-mono">{pack.version}</span>
        </p>
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {pack.disclaimer}
        </p>
      </header>

      <form id={formId} onSubmit={analyze} aria-labelledby={`${formId}-title`} className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id={`${formId}-title`} className="text-lg font-semibold">
              Tham số
            </h2>
            <p className="text-sm text-muted">Sửa giá trị rồi phân tích tác động. Chưa có gì thay đổi cho đến khi bạn áp dụng.</p>
          </div>
        </div>
        {isDemo && (
          <p className="text-sm">
            Demo 2 đã điền sẵn: hạ <strong>ngưỡng sinh trắc học/lần</strong> từ 10.000.000 đ xuống 5.000.000 đ (kịch bản giả lập). Bạn
            có thể sửa giá trị khác.
          </p>
        )}
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface">
          {Object.entries(pack.params).map(([name, p]) => {
            const id = `${formId}-${name}`;
            const raw = digits(draft[name] ?? "");
            const changed = raw !== "" && Number(raw) !== p.value;
            return (
              <li key={name} className="grid gap-3 p-4 md:grid-cols-[1fr_16rem] md:items-start">
                <div className="min-w-0">
                  <label htmlFor={id} className="font-medium">
                    {pack.params_vi?.[name] ?? name}
                  </label>
                  <p className="font-mono text-xs text-muted">{name}</p>
                  <p className="mt-1 text-sm text-muted">Nguồn: {p.source}</p>
                </div>
                <div>
                  <input
                    id={id}
                    name={name}
                    data-tour={name === DEMO2.param ? "param" : undefined}
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    value={draft[name] ?? ""}
                    onChange={(e) => onDraft(name, e.target.value)}
                    onBlur={() => raw && onDraft(name, formatInt(Number(raw)))}
                    aria-describedby={`${id}-hint`}
                    className={`min-h-12 w-full rounded-xl border bg-background px-3 text-right tabular-nums ${
                      changed ? "border-accent ring-1 ring-accent" : "border-zinc-400 dark:border-zinc-600"
                    }`}
                  />
                  <p id={`${id}-hint`} className="mt-1 text-right text-xs text-muted">
                    {changed ? (
                      <>
                        Hiện hành {fmtParam(p.value, p.unit)} → <strong className="text-accent">{fmtParam(Number(raw), p.unit)}</strong>
                      </>
                    ) : (
                      `Đơn vị: ${p.unit === "VND" ? "đồng" : p.unit === "s" ? "giây" : p.unit}`
                    )}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            data-tour="analyze"
            disabled={busy !== null || pending.length === 0}
            className="min-h-12 rounded-xl bg-accent px-6 font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-zinc-950"
          >
            {busy === "analyze" ? "Đang kiểm chứng lại bộ luật…" : "Phân tích tác động"}
          </button>
          <p className="text-sm text-muted" role="status">
            {pending.length === 0 ? "Chưa sửa tham số nào." : `${pending.length} tham số sẽ đổi.`}
          </p>
        </div>
      </form>

      {error && (
        <p role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-danger dark:border-red-900 dark:bg-red-950">
          {error}
        </p>
      )}

      <section aria-labelledby={`${formId}-inv`} className="space-y-3">
        <div>
          <h2 id={`${formId}-inv`} className="text-lg font-semibold">
            Invariant
          </h2>
          <p className="text-sm text-muted">Đặc tả mà toàn bộ bộ luật phải thỏa; Z3 kiểm chứng trên mọi giao dịch trong miền.</p>
        </div>
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface">
          {pack.invariants.map((inv) => (
            <li key={inv.id} className="grid gap-1 p-4 md:grid-cols-[9rem_1fr]">
              <p className="font-mono text-sm font-semibold">{inv.id}</p>
              <div>
                <p className="text-sm">{pack.invariants_vi?.[inv.id] ?? inv.type}</p>
                <p className="mt-1 text-xs text-muted">Nguồn: {inv.source}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {impact && (
        <section aria-labelledby={`${formId}-impact`} className="space-y-6">
          <div className="space-y-3 rounded-2xl border border-line bg-surface p-5">
            <h2 id={`${formId}-impact`} ref={resultsRef} tabIndex={-1} className="text-xl font-bold tracking-tight">
              Tác động của thay đổi
            </h2>
            <ul className="space-y-1">
              {impact.changes.map((c) =>
                c.op === "set_param" ? (
                  <li key={c.param} className="text-base">
                    {c.label_vi}: <span className="tabular-nums text-muted line-through">{fmtParam(c.old, c.unit)}</span> →{" "}
                    <strong className="tabular-nums">{fmtParam(c.new, c.unit)}</strong>
                  </li>
                ) : null,
              )}
            </ul>
            <div className="flex flex-wrap items-center gap-3">
              <VerdictBadge verdict={impact.verify_after.verdict} />
              <span className="text-sm text-muted">
                Kiểm chứng lại {impact.verify_after.checked.rules.length} luật với {impact.verify_after.checked.invariants.length}{" "}
                invariant của pack mới · {impact.ms} ms
              </span>
            </div>
            <ul className="flex flex-wrap gap-2 text-sm" aria-label="Phân loại luật">
              <li className="rounded-full bg-red-50 px-3 py-1 font-semibold text-danger ring-1 ring-red-200 dark:bg-red-950 dark:ring-red-900">
                ❌ {impact.counts.incompatible} không còn tương thích
              </li>
              {impact.counts.review > 0 && (
                <li className="rounded-full bg-amber-50 px-3 py-1 font-semibold text-warn ring-1 ring-amber-200 dark:bg-amber-950 dark:ring-amber-900">
                  ⚠️ {impact.counts.review} cần xem lại
                </li>
              )}
              {impact.counts.adaptive > 0 && (
                <li className="rounded-full bg-emerald-50 px-3 py-1 font-semibold text-ok ring-1 ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-900">
                  ✅ {impact.counts.adaptive} tự thích ứng
                </li>
              )}
              <li className="rounded-full px-3 py-1 text-muted ring-1 ring-line">{impact.counts.unaffected} không bị ảnh hưởng</li>
            </ul>
            <FrictionLine impact={impact} />
          </div>

          {byCat("incompatible").map((r) => (
            <AffectedRuleCard
              key={r.id}
              r={r}
              catalog={catalog}
              applied={applied}
              savedVersion={saved[r.id]}
              busy={busy !== null}
              onSave={() => saveFix(r)}
            />
          ))}
          {byCat("review").map((r) => (
            <AffectedRuleCard key={r.id} r={r} catalog={catalog} applied={applied} busy={busy !== null} />
          ))}

          {byCat("adaptive").length > 0 && (
            <div className="space-y-3 rounded-2xl border border-line bg-surface p-5">
              <h3 className="font-semibold">✅ Luật tự thích ứng — tham chiếu tham số nên tự đúng theo giá trị mới</h3>
              <ul className="space-y-3">
                {byCat("adaptive").map((r) => (
                  <li key={r.id}>
                    <p className="font-mono text-sm font-semibold">
                      {r.id} <span className="font-sans font-normal">{r.name}</span>
                    </p>
                    <RuleSentence render={r.render_after} compact />
                  </li>
                ))}
              </ul>
            </div>
          )}

          <DiffSection impact={impact} catalog={catalog} />

          <details className="rounded-2xl border border-line bg-surface p-5 text-sm">
            <summary className="cursor-pointer font-medium">{impact.counts.unaffected} luật không bị ảnh hưởng</summary>
            <ul className="mt-3 space-y-1">
              {byCat("unaffected").map((r) => (
                <li key={r.id}>
                  <span className="font-mono font-semibold">{r.id}</span> {r.name}
                </li>
              ))}
            </ul>
          </details>

          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-5">
            {applied ? (
              <p role="status" className="font-semibold text-ok">
                ✅ Đã áp dụng Policy Pack phiên bản <span className="font-mono">{applied}</span>.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => dialogRef.current?.showModal()}
                  disabled={busy !== null}
                  className="min-h-12 rounded-xl border-2 border-accent px-5 font-semibold text-accent hover:bg-violet-50 disabled:opacity-50 dark:hover:bg-violet-950"
                >
                  Áp dụng pack {nextVersion}
                </button>
                <p className="text-sm text-muted">Tạo phiên bản pack mới trong sandbox; phiên bản cũ vẫn được lưu để truy vết.</p>
              </>
            )}
          </div>

          <dialog
            ref={dialogRef}
            aria-labelledby={`${formId}-dialog`}
            onClose={() => {
              const ok = dialogRef.current?.returnValue === "apply";
              if (dialogRef.current) dialogRef.current.returnValue = "";
              if (ok) void applyPack();
            }}
            className="m-auto w-[min(32rem,calc(100%-2rem))] rounded-2xl border border-line bg-surface p-6 text-foreground backdrop:bg-black/50"
          >
            <h1 id={`${formId}-dialog`} className="text-lg font-bold">
              Áp dụng Policy Pack {nextVersion}?
            </h1>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {impact.changes.map((c) =>
                c.op === "set_param" ? (
                  <li key={c.param}>
                    {c.label_vi}: {fmtParam(c.old, c.unit)} → {fmtParam(c.new, c.unit)}
                  </li>
                ) : null,
              )}
            </ul>
            {impact.counts.incompatible > 0 && (
              <p className="mt-3 text-sm text-danger">
                {impact.counts.incompatible} luật sẽ không còn tương thích cho đến khi bạn lưu bản sửa.
              </p>
            )}
            <form method="dialog" className="mt-5 flex flex-wrap justify-end gap-3">
              <button value="cancel" autoFocus className="min-h-11 rounded-xl border border-line px-4 font-medium hover:bg-background">
                Hủy
              </button>
              <button value="apply" className="min-h-11 rounded-xl bg-accent px-4 font-semibold text-white hover:opacity-90 dark:text-zinc-950">
                Áp dụng pack
              </button>
            </form>
          </dialog>
        </section>
      )}
    </div>
  );
}

function FrictionLine({ impact }: { impact: PackImpact }) {
  const d = impact.friction.delta.friction_biometric;
  const days = impact.friction.days.length;
  return (
    <p className="text-base" data-tour="friction">
      Ma sát:{" "}
      <strong className="tabular-nums">
        {d >= 0 ? "+" : "−"}
        {formatInt(Math.abs(d))} giao dịch hợp lệ
      </strong>{" "}
      phải xác thực sinh trắc học ({formatInt(impact.friction.before.friction_biometric)} →{" "}
      {formatInt(impact.friction.after.friction_biometric)} trên {days} ngày dữ liệu).{" "}
      <span className="text-xs text-muted">(hệ thống tính)</span>
    </p>
  );
}

function AffectedRuleCard({
  r,
  catalog,
  applied,
  savedVersion,
  busy,
  onSave,
}: {
  r: ImpactRule;
  catalog: Catalog | null;
  applied: string | null;
  savedVersion?: number;
  busy: boolean;
  onSave?: () => void;
}) {
  const bad = r.category === "incompatible";
  return (
    <article
      aria-labelledby={`impact-${r.id}`}
      data-tour={bad ? "incompatible" : undefined}
      className={`space-y-4 rounded-2xl border-2 bg-surface p-5 ${bad ? "border-red-300 dark:border-red-900" : "border-amber-300 dark:border-amber-800"}`}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`impact-${r.id}`} className="text-lg font-semibold">
          <span className="font-mono">{r.id}</span> — {r.name}
        </h3>
        <span className={`text-sm font-semibold ${bad ? "text-danger" : "text-warn"}`}>
          {bad ? "❌ Không còn tương thích" : "⚠️ Cần xem lại"}
        </span>
      </header>
      <RuleSentence render={r.render_before} compact />
      {r.reasons.map((reason, i) => (
        <div key={i} className="space-y-3">
          <p className="text-sm">{reason.message_vi}</p>
          {reason.counterexample && (
            <CounterexampleCard
              check={reason}
              catalog={catalog}
              title={reason.outcomes ? "Giao dịch nhân chứng (do hệ thống tìm)" : undefined}
            />
          )}
          {reason.grounding && (
            <GroundingLine
              g={reason.grounding}
              what={reason.code === "STALE_LITERAL" ? "khớp luật khác đi chỉ vì mốc viết cứng" : undefined}
            />
          )}
        </div>
      ))}
      {r.fix?.rule && (
        <div className="space-y-3 rounded-xl border border-line bg-background p-4">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            Bản sửa tất định
            <span className="rounded-full border border-line px-2 py-0.5 text-xs font-normal">Tất định · không dùng AI</span>
            {r.fix.passes ? <VerdictBadge verdict={r.fix.verdict} /> : <VerdictBadge verdict="FAIL" />}
          </p>
          <RuleSentence render={r.fix.rule.render!} compact />
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {r.fix.notes_vi.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
          {onSave &&
            (savedVersion ? (
              <p role="status" className="text-sm font-semibold text-ok">
                ✅ Đã lưu {r.id} phiên bản {savedVersion}.
              </p>
            ) : (
              <button
                type="button"
                data-tour="fix"
                onClick={onSave}
                disabled={busy || !r.fix.passes}
                className="min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-zinc-950"
              >
                {applied ? "Lưu bản sửa" : "Áp dụng pack mới và lưu bản sửa"}
              </button>
            ))}
        </div>
      )}
    </article>
  );
}

function DiffSection({ impact, catalog }: { impact: PackImpact; catalog: Catalog | null }) {
  const diff = impact.semantic_diff;
  if (diff.status === "EQUIVALENT") return null;
  return (
    <div className="space-y-4 rounded-2xl border border-line bg-surface p-5">
      <div>
        <h3 className="font-semibold">Giao dịch đổi kết quả (semantic diff)</h3>
        <p className="text-sm text-muted">{diff.message_vi}</p>
      </div>
      <ul className="space-y-4">
        {diff.diffs.map((k) => (
          <li key={k.label_vi} className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <p className="font-medium">{k.label_vi}</p>
              <p className="text-sm text-muted">
                {DECISION_VI[k.before.decision]} · {AUTH_VI[k.before.auth]} → {DECISION_VI[k.after.decision]} ·{" "}
                {AUTH_VI[k.after.auth]}
              </p>
              {k.data && (
                <p className="text-sm">
                  <strong className="tabular-nums">
                    {formatInt(k.data.tx_count)} giao dịch · {formatVnd(k.data.amount_sum)}
                  </strong>{" "}
                  trong dữ liệu, trong đó {formatInt(k.data.by_label.LEGIT ?? 0)} hợp lệ.{" "}
                  <span className="text-xs text-muted">(hệ thống tính)</span>
                </p>
              )}
            </div>
            <CounterexampleCard check={{ counterexample: k.counterexample }} catalog={catalog} title="Giao dịch nhân chứng (Z3)" />
          </li>
        ))}
      </ul>
    </div>
  );
}
