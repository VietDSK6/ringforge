"use client";

import { useParams, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { Callout } from "@/components/Callout";
import { CounterexampleCard } from "@/components/CounterexampleCard";
import { GroundingLine } from "@/components/GroundingLine";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";
import { Icon } from "@/components/Icon";
import { PageSkeleton } from "@/components/PageSkeleton";
import { RegulationInterpreter } from "@/components/RegulationInterpreter";
import { RuleSentence } from "@/components/RuleSentence";
import { SourceTag } from "@/components/SourceTag";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { AUTH_VI, DECISION_VI, formatInt, formatVnd } from "@/lib/format";
import type { Catalog, ImpactRule, PackImpact, PackRepairResponse, PatchOp, PolicyPack, Rule } from "@/lib/types";

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
  // Bản vá AI đề xuất mà người dùng chọn dùng: nguồn ghi kèm tham số + invariant mới (FR-P4).
  const [aiSources, setAiSources] = useState<Record<string, string>>({});
  const [aiInvariants, setAiInvariants] = useState<Extract<PatchOp, { op: "add_invariant" }>[]>([]);
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
      const source = aiSources[name] ?? (isDemo ? DEMO_SOURCE : undefined);
      return [source ? { ...op, source } : op];
    });
  }

  function takeAiPatch(ops: PatchOp[]) {
    const sources: Record<string, string> = {};
    const next = { ...draft };
    for (const op of ops) {
      if (op.op === "set_param") {
        next[op.param] = formatInt(op.value);
        if (op.source) sources[op.param] = op.source;
      }
    }
    setDraft(next);
    setAiSources(sources);
    setAiInvariants(ops.filter((o): o is Extract<PatchOp, { op: "add_invariant" }> => o.op === "add_invariant"));
    setImpact(null);
    requestAnimationFrame(() => document.getElementById(`${formId}-title`)?.scrollIntoView({ block: "start" }));
  }

  const pending: PatchOp[] = pack ? [...buildPatch(pack), ...aiInvariants] : [];

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

  /** Áp dụng pack mới (nếu chưa) rồi lưu các luật của bản sửa — bản sửa đúng theo pack MỚI nên phải áp dụng trước. */
  async function saveRuleFix(ruleId: string, rules: Rule[]) {
    if (!(await applyPack())) return;
    try {
      let version: number | undefined;
      for (const rule of rules) {
        const res = await api.saveRule(sid, withoutRender(rule));
        if (res.saved && res.rule && rule.id === ruleId) version = res.rule.version;
      }
      if (version) setSaved((s) => ({ ...s, [ruleId]: version! }));
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
      <Callout tone="fail" role="alert" title="Không tải được Policy Pack">
        <p>{error}</p>
      </Callout>
    );
  }
  if (!pack) return <PageSkeleton label="Đang tải Policy Pack…" rows={4} />;

  const byCat = (c: ImpactRule["category"]) => impact?.rules.filter((r) => r.category === c) ?? [];
  const nextVersion = impact?.pack_after.version;

  return (
    <div className="space-y-8">
      <GuidedTour id="demo2" steps={TOUR} enabled={isDemo} />
      <header className="space-y-3">
        <div>
          <h1 className="page-title">Policy Pack</h1>
          <p className="page-lede flex flex-wrap items-center gap-2">
            <span>{pack.id}</span>
            <span className="chip font-mono text-[0.75rem]">phiên bản {pack.version}</span>
          </p>
        </div>
        <Callout tone="warn">{pack.disclaimer}</Callout>
      </header>

      <form id={formId} onSubmit={analyze} aria-labelledby={`${formId}-title`} className="space-y-4">
        <div>
          <h2 id={`${formId}-title`} className="section-title scroll-mt-16">
            Tham số
          </h2>
          <p className="section-lede">Sửa giá trị rồi phân tích tác động. Chưa có gì thay đổi cho đến khi bạn áp dụng.</p>
        </div>
        {isDemo && (
          <Callout tone="info">
            Demo 2 đã điền sẵn: hạ <strong>ngưỡng sinh trắc học/lần</strong> từ 10.000.000 đ xuống 5.000.000 đ (kịch bản giả lập). Bạn có
            thể sửa giá trị khác.
          </Callout>
        )}
        <ul className="panel divide-y divide-line">
          {Object.entries(pack.params).map(([name, p]) => {
            const id = `${formId}-${name}`;
            const raw = digits(draft[name] ?? "");
            const changed = raw !== "" && Number(raw) !== p.value;
            return (
              <li
                key={name}
                className={`grid gap-3 p-4 sm:px-5 md:grid-cols-[1fr_17rem] md:items-start ${changed ? "bg-accent-soft/50" : ""}`}
              >
                <div className="min-w-0">
                  <label htmlFor={id} className="font-medium">
                    {pack.params_vi?.[name] ?? name}
                  </label>
                  <p className="font-mono text-xs text-muted">{name}</p>
                  <p className="mt-1 text-[0.8125rem] text-muted">Nguồn: {p.source}</p>
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
                    className={`field num min-h-12 text-right text-[1.0625rem] font-medium ${changed ? "border-accent! ring-1 ring-accent" : ""}`}
                  />
                  <p id={`${id}-hint`} className="num mt-1 text-right text-xs text-muted">
                    {changed ? (
                      <>
                        Hiện hành <span className="line-through">{fmtParam(p.value, p.unit)}</span> →{" "}
                        <strong className="text-accent">{fmtParam(Number(raw), p.unit)}</strong>
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
        {aiInvariants.length > 0 && (
          <ul className="space-y-2" aria-label="Invariant mới từ bản vá AI đề xuất">
            {aiInvariants.map((op) => (
              <li key={op.invariant.id} className="flex flex-wrap items-center gap-3 rounded-md border border-accent-line bg-accent-soft px-3.5 py-1.5 text-sm">
                <span>
                  Thêm invariant <span className="font-mono font-semibold">{op.invariant.id}</span> (AI đề xuất)
                </span>
                <button
                  type="button"
                  onClick={() => setAiInvariants((xs) => xs.filter((x) => x.invariant.id !== op.invariant.id))}
                  className="btn btn-ghost btn-sm ml-auto"
                >
                  Bỏ
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" data-tour="analyze" disabled={busy !== null || pending.length === 0} className="btn btn-primary btn-lg">
            {busy === "analyze" && <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
            {busy === "analyze" ? "Đang kiểm chứng lại bộ luật…" : "Phân tích tác động"}
          </button>
          <p className="text-sm text-muted" role="status">
            {pending.length === 0 ? "Chưa có thay đổi nào." : `${pending.length} thay đổi sẽ được phân tích.`}
          </p>
        </div>
      </form>

      <RegulationInterpreter sid={sid} onUse={takeAiPatch} />

      {error && (
        <Callout tone="fail" role="alert">
          {error}
        </Callout>
      )}

      {impact && (
        <section aria-labelledby={`${formId}-impact`} className="space-y-5">
          <div className="panel space-y-5 p-4 sm:p-5">
            <div className="space-y-2">
              <h2 id={`${formId}-impact`} ref={resultsRef} tabIndex={-1} className="page-title text-[1.375rem] outline-none">
                Tác động của thay đổi
              </h2>
              <ul className="space-y-1">
                {impact.changes.map((c) =>
                  c.op === "set_param" ? (
                    <li key={c.param} className="text-base">
                      {c.label_vi}: <span className="num text-muted line-through">{fmtParam(c.old, c.unit)}</span> →{" "}
                      <strong className="num">{fmtParam(c.new, c.unit)}</strong>
                    </li>
                  ) : null,
                )}
              </ul>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <VerdictBadge verdict={impact.verify_after.verdict} large />
              <span className="num text-sm text-muted">
                Kiểm chứng lại {impact.verify_after.checked.rules.length} luật với {impact.verify_after.checked.invariants.length} invariant
                của pack mới · {impact.ms} ms
              </span>
            </div>
            <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4" aria-label="Phân loại luật">
              <CountCell n={impact.counts.incompatible} label="không còn tương thích" tone="fail" />
              <CountCell n={impact.counts.review} label="cần xem lại" tone="warn" />
              <CountCell n={impact.counts.adaptive} label="tự thích ứng" tone="pass" />
              <CountCell n={impact.counts.unaffected} label="không bị ảnh hưởng" />
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
              onSave={() => r.fix?.rule && saveRuleFix(r.id, [r.fix.rule])}
              ai={{ sid, patch, onSaveRules: (rules) => saveRuleFix(r.id, rules) }}
            />
          ))}
          {byCat("review").map((r) => (
            <AffectedRuleCard key={r.id} r={r} catalog={catalog} applied={applied} busy={busy !== null} />
          ))}

          {byCat("adaptive").length > 0 && (
            <div className="panel overflow-hidden">
              <h3 className="border-b border-line px-4 py-3 font-semibold sm:px-5">
                Luật tự thích ứng — tham chiếu tham số nên tự đúng theo giá trị mới
              </h3>
              <ul className="divide-y divide-line">
                {byCat("adaptive").map((r) => (
                  <li key={r.id} className="space-y-1 px-4 py-3 sm:px-5">
                    <p className="text-sm">
                      <span className="font-mono font-semibold">{r.id}</span> <span className="font-medium">{r.name}</span>
                    </p>
                    <RuleSentence render={r.render_after} compact />
                  </li>
                ))}
              </ul>
            </div>
          )}

          <DiffSection impact={impact} catalog={catalog} />

          <details className="group panel text-sm">
            <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 px-4 font-medium sm:px-5 [&::-webkit-details-marker]:hidden">
              <Icon name="arrow" className="size-3.5 text-muted transition-transform group-open:rotate-90" />
              {impact.counts.unaffected} luật không bị ảnh hưởng
            </summary>
            <ul className="space-y-1 border-t border-line px-4 py-3 sm:px-5">
              {byCat("unaffected").map((r) => (
                <li key={r.id}>
                  <span className="font-mono font-semibold">{r.id}</span> {r.name}
                </li>
              ))}
            </ul>
          </details>

          <div className="panel flex flex-wrap items-center gap-x-4 gap-y-3 p-4 sm:p-5">
            {applied ? (
              <p role="status" className="font-semibold text-pass">
                Đã áp dụng Policy Pack phiên bản <span className="font-mono">{applied}</span>.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => dialogRef.current?.showModal()}
                  disabled={busy !== null}
                  className="btn btn-outline-accent btn-lg"
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
            className="m-auto w-[min(32rem,calc(100%-2rem))] rounded-xl border border-line bg-surface p-6 text-foreground shadow-pop"
          >
            <h1 id={`${formId}-dialog`} className="text-lg font-bold">
              Áp dụng Policy Pack {nextVersion}?
            </h1>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {impact.changes.map((c) =>
                c.op === "set_param" ? (
                  <li key={c.param} className="num">
                    {c.label_vi}: {fmtParam(c.old, c.unit)} → {fmtParam(c.new, c.unit)}
                  </li>
                ) : null,
              )}
            </ul>
            {impact.counts.incompatible > 0 && (
              <Callout tone="fail" className="mt-4">
                {impact.counts.incompatible} luật sẽ không còn tương thích cho đến khi bạn lưu bản sửa.
              </Callout>
            )}
            <form method="dialog" className="mt-6 flex flex-wrap justify-end gap-3">
              <button value="cancel" autoFocus className="btn btn-secondary">
                Hủy
              </button>
              <button value="apply" className="btn btn-primary">
                Áp dụng pack
              </button>
            </form>
          </dialog>
        </section>
      )}

      <section aria-labelledby={`${formId}-inv`} className="space-y-3">
        <div>
          <h2 id={`${formId}-inv`} className="section-title">
            Invariant
          </h2>
          <p className="section-lede">Đặc tả mà toàn bộ bộ luật phải thỏa; Z3 kiểm chứng trên mọi giao dịch trong miền.</p>
        </div>
        <ul className="panel divide-y divide-line">
          {pack.invariants.map((inv) => (
            <li key={inv.id} className="grid gap-1 p-4 sm:px-5 md:grid-cols-[10rem_1fr] md:gap-4">
              <p className="font-mono text-sm font-semibold">{inv.id}</p>
              <div>
                <p className="text-sm leading-6">{pack.invariants_vi?.[inv.id] ?? inv.type}</p>
                <p className="mt-1 text-xs text-muted">Nguồn: {inv.source}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function CountCell({ n, label, tone }: { n: number; label: string; tone?: "fail" | "warn" | "pass" }) {
  const color = n > 0 && tone ? { fail: "text-fail", warn: "text-warn", pass: "text-pass" }[tone] : "text-muted";
  return (
    <li className="bg-surface p-3">
      <div>
        <p className={`num text-2xl leading-8 font-bold ${n > 0 && tone ? color : ""}`}>{n}</p>
        <p className="text-[0.8125rem] text-muted">{label}</p>
      </div>
    </li>
  );
}

function FrictionLine({ impact }: { impact: PackImpact }) {
  const d = impact.friction.delta.friction_biometric;
  const days = impact.friction.days.length;
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-sunken p-4" data-tour="friction">
      <div className="space-y-0.5">
        <p className="label">Ma sát</p>
        <p className="text-base">
          <strong className="num text-2xl font-bold tracking-tight">
            {d >= 0 ? "+" : "−"}
            {formatInt(Math.abs(d))} giao dịch hợp lệ
          </strong>{" "}
          phải xác thực sinh trắc học
        </p>
        <p className="num text-sm text-muted">
          {formatInt(impact.friction.before.friction_biometric)} → {formatInt(impact.friction.after.friction_biometric)} trên {days} ngày
          dữ liệu
        </p>
      </div>
      <SourceTag source="system" />
    </div>
  );
}

function AffectedRuleCard({
  r,
  catalog,
  applied,
  savedVersion,
  busy,
  onSave,
  ai,
}: {
  r: ImpactRule;
  catalog: Catalog | null;
  applied: string | null;
  savedVersion?: number;
  busy: boolean;
  onSave?: () => void;
  ai?: { sid: string; patch: PatchOp[]; onSaveRules: (rules: Rule[]) => void };
}) {
  const bad = r.category === "incompatible";
  return (
    <article
      aria-labelledby={`impact-${r.id}`}
      data-tour={bad ? "incompatible" : undefined}
      className={`panel overflow-hidden ${bad ? "border-fail-line" : "border-warn-line"}`}
    >
      <header
        className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b px-4 py-3 sm:px-5 ${
          bad ? "border-fail-line bg-fail-soft" : "border-warn-line bg-warn-soft"
        }`}
      >
        <h3 id={`impact-${r.id}`} className="text-base font-semibold">
          <span className="font-mono">{r.id}</span> — {r.name}
        </h3>
        <span className={`text-sm font-semibold ${bad ? "text-fail" : "text-warn"}`}>
          {bad ? "Không còn tương thích" : "Cần xem lại"}
        </span>
      </header>
      <div className="space-y-4 p-4 sm:p-5">
        <RuleSentence render={r.render_before} compact />
        {r.reasons.map((reason, i) => (
          <div key={i} className="space-y-3">
            <p className="max-w-[75ch] text-sm leading-6">{reason.message_vi}</p>
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
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
          </div>
        ))}
        {r.fix?.rule && (
          <div className="space-y-3 rounded-lg border border-line bg-sunken p-4">
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              Bản sửa tất định
              <SourceTag source="det" label="Tất định · không dùng AI" />
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
                <p role="status" className="text-sm font-semibold text-pass">
                  Đã lưu {r.id} phiên bản {savedVersion}.
                </p>
              ) : (
                <button type="button" data-tour="fix" onClick={onSave} disabled={busy || !r.fix.passes} className="btn btn-primary">
                  {applied ? "Lưu bản sửa" : "Áp dụng pack mới và lưu bản sửa"}
                </button>
              ))}
          </div>
        )}
        {ai && !savedVersion && <AiPackRepair ruleId={r.id} applied={applied} busy={busy} {...ai} />}
      </div>
    </article>
  );
}

const LLM_NOTE: Record<string, string> = {
  unavailable: "AI hiện không khả dụng — chỉ có bản sửa tất định ở trên.",
  quota: "Đã hết lượt gọi AI hôm nay — chỉ có bản sửa tất định ở trên.",
  error: "Gọi AI bị lỗi — chỉ có bản sửa tất định ở trên.",
};

/** AI đề xuất bản sửa cho luật không còn tương thích; mọi bản được chấm lại theo Policy Pack MỚI trước khi hiện. */
function AiPackRepair({
  sid,
  patch,
  ruleId,
  applied,
  busy,
  onSaveRules,
}: {
  sid: string;
  patch: PatchOp[];
  ruleId: string;
  applied: string | null;
  busy: boolean;
  onSaveRules: (rules: Rule[]) => void;
}) {
  const [data, setData] = useState<PackRepairResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.packRepair(sid, patch, ruleId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được bản sửa.");
    } finally {
      setLoading(false);
    }
  }

  const aiCands = data?.candidates.filter((c) => c.source === "ai") ?? [];
  const mark = (ok: boolean, warn = false) => (
    <Icon name={ok ? "check" : warn ? "alert" : "x"} className={`mt-1 size-3.5 ${ok ? "text-pass" : warn ? "text-warn" : "text-fail"}`} />
  );
  return (
    <div className="space-y-3">
      {!data && (
        <button type="button" onClick={run} disabled={loading || busy} className="btn btn-outline-accent">
          {loading && <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
          {loading ? "AI đang đề xuất, hệ thống kiểm chứng lại từng bản…" : "Sửa bằng AI"}
        </button>
      )}
      {error && (
        <Callout tone="fail" role="alert">
          {error}
        </Callout>
      )}
      {data && (
        <div className="space-y-3" role="status">
          {LLM_NOTE[data.llm] && <Callout tone="warn">{LLM_NOTE[data.llm]}</Callout>}
          {aiCands.map((c) => (
            <div key={c.rank} className="space-y-3 rounded-lg border border-accent-line bg-surface p-4">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                Bản AI #{c.rank}
                <SourceTag source="ai" label="AI đề xuất · đã kiểm chứng lại" />
                <VerdictBadge verdict={c.verdict} />
              </p>
              {c.rules.map((rule) => rule.render && <RuleSentence key={rule.id} render={rule.render} compact />)}
              <ul className="space-y-1 text-sm">
                <li className="flex gap-2">
                  {mark(c.stale_params.length === 0)}
                  {c.stale_params.length === 0 ? "Không còn mốc viết cứng giá trị cũ" : "Vẫn viết cứng giá trị cũ"}
                </li>
                {c.relations.map((rel) => (
                  <li key={rel.invariant} className="flex gap-2">
                    {mark(rel.kept, true)}
                    {rel.message_vi}
                  </li>
                ))}
                <li className="flex gap-2">
                  {mark(c.uses_param, true)}
                  {c.uses_param ? "Tham chiếu tham số Policy Pack" : "Không tham chiếu tham số"}
                </li>
                <li className="num pl-5.5 text-muted">
                  Δ L_net: {c.delta.l_net === 0 ? "không đổi" : `${c.delta.l_net > 0 ? "+" : "−"}${formatVnd(Math.abs(c.delta.l_net))}`} · Δ giao
                  dịch thật phải sinh trắc học: {formatInt(c.delta.friction_biometric)} <span className="text-xs">(hệ thống tính)</span>
                </li>
              </ul>
              {c.rationale_vi && <p className="text-sm text-muted">{c.rationale_vi}</p>}
              <button type="button" onClick={() => onSaveRules(c.rules)} disabled={busy} className="btn btn-primary">
                {applied ? "Lưu bản này" : "Áp dụng pack mới và lưu bản này"}
              </button>
            </div>
          ))}
          {data.llm === "used" && aiCands.length === 0 && (
            <p className="text-sm">Chưa có bản AI nào qua kiểm chứng; dùng bản sửa tất định ở trên.</p>
          )}
          {data.rejected.length > 0 && (
            <details className="group text-sm text-muted">
              <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 hover:text-foreground [&::-webkit-details-marker]:hidden">
                <Icon name="arrow" className="size-3.5 transition-transform group-open:rotate-90" />
                {data.rejected.length} đề xuất khác bị loại (bấm xem lý do)
              </summary>
              <ul className="mt-1 list-disc space-y-1 pl-10">
                {data.rejected.map((x, i) => (
                  <li key={i}>
                    {x.source === "ai" ? "AI" : "Tất định"} · {x.strategy}: {x.reason_vi}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function DiffSection({ impact, catalog }: { impact: PackImpact; catalog: Catalog | null }) {
  const diff = impact.semantic_diff;
  if (diff.status === "EQUIVALENT") return null;
  return (
    <div className="panel space-y-4 p-4 sm:p-5">
      <div>
        <h3 className="section-title">Giao dịch đổi kết quả (semantic diff)</h3>
        <p className="section-lede">{diff.message_vi}</p>
      </div>
      <ul className="divide-y divide-line">
        {diff.diffs.map((k) => (
          <li key={k.label_vi} className="grid gap-4 py-4 first:pt-0 last:pb-0 md:grid-cols-2">
            <div className="space-y-1.5">
              <p className="font-medium">{k.label_vi}</p>
              <p className="text-sm text-muted">
                {DECISION_VI[k.before.decision]} · {AUTH_VI[k.before.auth]} → {DECISION_VI[k.after.decision]} · {AUTH_VI[k.after.auth]}
              </p>
              {k.data && (
                <p className="text-sm">
                  <strong className="num">
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
