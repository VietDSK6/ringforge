"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Callout } from "@/components/Callout";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";
import { LnetStackedBar, type LnetRow } from "@/components/LnetStackedBar";
import { PageSkeleton } from "@/components/PageSkeleton";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ApiError, api } from "@/lib/api";
import { formatInt, formatVnd } from "@/lib/format";
import type { Assumptions, BacktestResponse, BacktestResult } from "@/lib/types";

type Window = 15 | 30 | 60;
type Action = "HOLD" | "BLOCK";

interface VariantForm {
  key: number;
  window: Window;
  senders: number;
  maxAge: number | null; // null = không xét tuổi tài khoản nhận
  p2pOnly: boolean;
  action: Action;
}

const MAX_VARIANTS = 4;
const RULE_ID = "FR-05";

// Demo 3 (docs/01 mục 7): chặn khoản nạn nhân chuyển vào tài khoản nhận mới đang gom tiền từ nhiều người.
const PRESETS: Omit<VariantForm, "key">[] = [
  { window: 15, senders: 2, maxAge: 14, p2pOnly: true, action: "HOLD" },
  { window: 30, senders: 2, maxAge: 14, p2pOnly: true, action: "HOLD" },
  { window: 60, senders: 2, maxAge: 14, p2pOnly: true, action: "HOLD" },
  { window: 60, senders: 2, maxAge: null, p2pOnly: true, action: "BLOCK" },
];

const DEFAULT_ASSUMPTIONS: Assumptions = {
  hold_stop_bp: 5_000,
  c_review_block: 30_000,
  churn_hold_bp: 500,
  churn_block_bp: 3_000,
  margin_bp: 50,
};

const pct = (bp: number) => `${(bp / 100).toLocaleString("vi-VN", { maximumFractionDigits: 2 })}%`;

const SLIDERS: { key: keyof Assumptions; label: string; min: number; max: number; step: number; fmt: (v: number) => string }[] = [
  { key: "hold_stop_bp", label: "Hiệu quả khoảng dừng: tỷ lệ nạn nhân hủy khi bị giữ", min: 0, max: 10_000, step: 500, fmt: pct },
  { key: "c_review_block", label: "Chi phí duyệt mỗi giao dịch thật bị chặn", min: 0, max: 200_000, step: 5_000, fmt: formatVnd },
  { key: "churn_hold_bp", label: "Tỷ lệ khách thật bỏ giao dịch khi bị giữ", min: 0, max: 5_000, step: 100, fmt: pct },
  { key: "churn_block_bp", label: "Tỷ lệ khách thật bỏ giao dịch khi bị chặn", min: 0, max: 10_000, step: 500, fmt: pct },
  { key: "margin_bp", label: "Lợi nhuận mất trên mỗi đồng giao dịch bị bỏ", min: 0, max: 500, step: 10, fmt: pct },
];

const TOUR: TourStep[] = [
  { target: "variants", text: "Bốn phương án: cửa sổ 15, 30, 60 phút; giữ hay chặn." },
  { target: "results", text: "Hàng in đậm có L_net thấp nhất trong các phương án hợp lệ.", waiting: "Đang backtest…" },
  { target: "slider", text: "Kéo lên 100%: giữ lại hiệu quả như chặn, thứ hạng đổi." },
  { target: "scenarios", text: "Phân rã kịch bản: flash-sale cho thấy chặn nhầm giao dịch thật." },
  { target: "changeset", text: "Tạo change set để người duyệt ký trước khi bật.", advanceOn: "click" },
];

const ACTION_VI: Record<Action, string> = { HOLD: "Giữ 120 giây", BLOCK: "Chặn" };
const SCENARIO_ORDER = ["S1_MULE", "S2_ATO", "S3_FLASH_SALE", "S4_FAMILIAR_HIGH", "S0_NORMAL"];

function variantName(v: VariantForm, i: number): string {
  const parts = [`P${i + 1}`, `${v.window} phút`, v.action === "HOLD" ? "Giữ" : "Chặn"];
  if (v.maxAge === null) parts.push("mọi tuổi TK nhận");
  if (!v.p2pOnly) parts.push("mọi kênh");
  return parts.join(" · ");
}

function buildRule(v: VariantForm) {
  const all: Record<string, unknown>[] = [];
  if (v.maxAge !== null) all.push({ field: "receiver_account_age_days", op: "<", value: v.maxAge });
  all.push({ field: `receiver_distinct_senders_${v.window}m`, op: ">=", value: v.senders });
  if (v.p2pOnly) all.push({ field: "channel", op: "==", value: "P2P" });
  return {
    id: RULE_ID,
    name: "Tài khoản nhận mới gom tiền từ nhiều người",
    kind: "FRAUD",
    status: "CANDIDATE",
    when: { all },
    then: v.action === "HOLD" ? { decision: "HOLD", hold_seconds: 120 } : { decision: "BLOCK" },
  };
}

/** Số nguyên hợp lệ trong [lo, hi] thì trả về; đang gõ dở (rỗng, ngoài khoảng) thì null và báo lỗi tại ô. */
function commitInt(input: HTMLInputElement, lo: number, hi: number): number | null {
  const n = input.valueAsNumber;
  const ok = Number.isInteger(n) && n >= lo && n <= hi;
  input.setCustomValidity(ok ? "" : `Nhập số nguyên từ ${lo} đến ${hi}.`);
  return ok ? n : null;
}

/** So sánh phương án luật bằng L_net (docs/07 mục 3.5 — Demo 3). Mọi con số do backtest tính. */
export function CompareView() {
  const { sid } = useParams<{ sid: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const uid = useId();
  const nextKey = useRef(PRESETS.length);
  const [variants, setVariants] = useState<VariantForm[]>(() => PRESETS.map((p, key) => ({ ...p, key })));
  const [assumptions, setAssumptions] = useState<Assumptions>(DEFAULT_ASSUMPTIONS);
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [sent, setSent] = useState<typeof payload>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const payload = useMemo(
    () => variants.map((v, i) => ({ name: variantName(v, i), rule_changes: [{ op: "add", rule: buildRule(v) }] })),
    [variants],
  );

  // Tính lại khi đổi phương án hoặc kéo thanh trượt (debounce 300 ms, bỏ kết quả của yêu cầu cũ).
  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setRunning(true);
      try {
        const res = await api.backtest(sid, payload, assumptions, ctrl.signal);
        setData(res);
        setSent(payload);
        setError(null);
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof ApiError ? e.message : "Backtest thất bại.");
      } finally {
        if (!ctrl.signal.aborted) setRunning(false);
      }
    }, 300);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [sid, payload, assumptions]);

  async function proposeChangeSet(index: number) {
    const change = sent[index];
    if (!change) return;
    try {
      const cs = await api.createChangeSet(sid, [{ rule: change.rule_changes[0].rule }], `Phương án ${change.name} từ màn So sánh`);
      router.push(`/s/${sid}/review?cs=${cs.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được change set.");
    }
  }

  const update = (key: number, patch: Partial<VariantForm>) =>
    setVariants((vs) => vs.map((v) => (v.key === key ? { ...v, ...patch } : v)));

  const rows: { name: string; r: BacktestResult; rank?: number; eligible: boolean; verdict?: string; errors?: string[] }[] = data
    ? [
        { name: "Bộ luật hiện hành (không thêm luật)", r: data.baseline, eligible: data.baseline.valid },
        ...data.variants.flatMap((v) =>
          v.result
            ? [{ name: v.name, r: v.result, rank: v.rank, eligible: v.eligible, verdict: v.verify?.verdict, errors: v.verify?.errors }]
            : [],
        ),
      ]
    : [];
  const best = data?.variants.find((v) => v.rank === 1);
  const chartRows: LnetRow[] = rows.map((row, i) => ({
    label: i === 0 ? "Hiện hành" : row.name.split(" · ").slice(0, 3).join(" · "),
    fn_loss: row.r.fn_loss,
    review_cost: row.r.review_cost,
    churn_loss: row.r.churn_loss,
    l_net: row.r.l_net,
  }));

  return (
    <div className="space-y-8">
      <GuidedTour id="demo3" steps={TOUR} enabled={search.get("demo") === "3"} />
      <header>
        <h1 className="page-title">So sánh phương án</h1>
        <p className="page-lede">
          Luật <span className="font-mono text-foreground">{RULE_ID}</span> giữ hoặc chặn khoản chuyển cá nhân vào tài khoản nhận mới mở đang
          gom tiền từ nhiều người — kiểu nạn nhân chuyển cho mule lớp 1. Mỗi phương án được thêm vào bộ luật đang chạy, kiểm chứng bằng Z3
          rồi backtest trên 6 ngày dữ liệu tổng hợp.
        </p>
      </header>

      <section aria-labelledby={`${uid}-variants`} className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id={`${uid}-variants`} className="section-title">
            Phương án
          </h2>
          <button
            type="button"
            disabled={variants.length >= MAX_VARIANTS}
            onClick={() => setVariants((vs) => [...vs, { ...PRESETS[1], key: nextKey.current++ }])}
            className="btn btn-secondary btn-sm"
          >
            Thêm phương án
          </button>
        </div>
        <ul className="grid gap-4 xl:grid-cols-2" data-tour="variants">
          {variants.map((v, i) => {
            const id = `${uid}-v${v.key}`;
            const sentence = data?.variants[i]?.rules_vi?.[RULE_ID];
            return (
              <li key={v.key} className="panel">
                <fieldset className="space-y-4 p-4 sm:p-5">
                  <legend className="float-left flex w-full items-center justify-between gap-2">
                    <span className="font-semibold">{variantName(v, i)}</span>
                    {variants.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setVariants((vs) => vs.filter((x) => x.key !== v.key))}
                        className="btn btn-ghost btn-sm -mr-2"
                      >
                        Bỏ phương án này
                      </button>
                    )}
                  </legend>
                  <div className="clear-both flex flex-wrap items-end gap-x-6 gap-y-3">
                    <Segmented
                      caption="Cửa sổ"
                      label={`Cửa sổ thời gian của ${variantName(v, i)}`}
                      name={`${id}-w`}
                      options={([15, 30, 60] as Window[]).map((w) => ({ value: w, label: `${w} phút` }))}
                      value={v.window}
                      onChange={(w) => update(v.key, { window: w })}
                    />
                    <Segmented
                      caption="Hành động"
                      label={`Hành động của ${variantName(v, i)}`}
                      name={`${id}-act`}
                      options={(["HOLD", "BLOCK"] as Action[]).map((a) => ({ value: a, label: ACTION_VI[a] }))}
                      value={v.action}
                      onChange={(a) => update(v.key, { action: a })}
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label htmlFor={`${id}-s`} className="label">
                        Số người gửi khác nhau, từ
                      </label>
                      <input
                        id={`${id}-s`}
                        type="number"
                        min={1}
                        max={50}
                        defaultValue={v.senders}
                        onChange={(e) => {
                          const n = commitInt(e.currentTarget, 1, 50);
                          if (n !== null) update(v.key, { senders: n });
                        }}
                        className="field num mt-1"
                      />
                    </div>
                    <div>
                      <label htmlFor={`${id}-a`} className="label">
                        Tuổi tài khoản nhận dưới (ngày)
                      </label>
                      <input
                        key={v.maxAge === null ? "off" : "on"}
                        id={`${id}-a`}
                        type="number"
                        min={1}
                        max={3650}
                        defaultValue={v.maxAge ?? ""}
                        disabled={v.maxAge === null}
                        onChange={(e) => {
                          const n = commitInt(e.currentTarget, 1, 3650);
                          if (n !== null) update(v.key, { maxAge: n });
                        }}
                        className="field num mt-1"
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-x-6 text-sm">
                    <label className="inline-flex min-h-11 cursor-pointer items-center gap-2.5">
                      <input
                        type="checkbox"
                        className="size-4"
                        checked={v.maxAge === null}
                        onChange={(e) => update(v.key, { maxAge: e.target.checked ? null : 14 })}
                      />
                      Không xét tuổi tài khoản nhận
                    </label>
                    <label className="inline-flex min-h-11 cursor-pointer items-center gap-2.5">
                      <input type="checkbox" className="size-4" checked={v.p2pOnly} onChange={(e) => update(v.key, { p2pOnly: e.target.checked })} />
                      Chỉ chuyển tiền cá nhân
                    </label>
                  </div>
                  {sentence && <p className="well px-3 py-2.5 text-sm leading-6">{sentence}</p>}
                </fieldset>
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby={`${uid}-assume`} className="panel space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id={`${uid}-assume`} className="section-title">
            Giả định
          </h2>
          <span className="chip tone-warn">giả định — không phải số thật
          </span>
        </div>
        <div className="grid gap-x-10 gap-y-2 md:grid-cols-2">
          {SLIDERS.map((s) => {
            const id = `${uid}-${s.key}`;
            return (
              <div key={s.key}>
                <div className="flex items-baseline justify-between gap-4">
                  <label htmlFor={id} className="text-sm">
                    {s.label}
                  </label>
                  <output htmlFor={id} className="num shrink-0 text-sm font-semibold">
                    {s.fmt(assumptions[s.key])}
                  </output>
                </div>
                <input
                  id={id}
                  data-tour={s.key === "hold_stop_bp" ? "slider" : undefined}
                  type="range"
                  min={s.min}
                  max={s.max}
                  step={s.step}
                  value={assumptions[s.key]}
                  aria-valuetext={s.fmt(assumptions[s.key])}
                  onChange={(e) => setAssumptions((a) => ({ ...a, [s.key]: Number(e.target.value) }))}
                  className="range"
                />
              </div>
            );
          })}
        </div>
        <button type="button" onClick={() => setAssumptions(DEFAULT_ASSUMPTIONS)} className="btn btn-ghost btn-sm -ml-2.5">
          Về giả định mặc định
        </button>
      </section>

      <section aria-labelledby={`${uid}-results`} className="space-y-4" aria-busy={running}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id={`${uid}-results`} className="section-title">
            Kết quả
          </h2>
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            {running && <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent" />}
            {running ? "Đang kiểm chứng và backtest…" : data ? `Tính trong ${formatInt(data.ms)} ms · hệ thống tính` : ""}
          </p>
        </div>
        {error && (
          <Callout tone="fail" role="alert">
            {error}
          </Callout>
        )}
        {!data && !error && <PageSkeleton label="Đang kiểm chứng và backtest…" rows={5} />}
        {best && (
          <div className="panel flex flex-wrap items-center justify-between gap-x-8 gap-y-4 p-4 sm:p-5">
            <div className="min-w-0 space-y-1">
              <p className="text-sm text-muted">Tốt nhất theo L_net trong các phương án qua cổng invariant</p>
              <p className="text-lg font-semibold">{best.name}</p>
              <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <strong className="num text-3xl font-bold tracking-tight">{formatVnd(best.result!.l_net)}</strong>
                {best.delta && (
                  <span className={`num text-sm font-medium ${best.delta.l_net <= 0 ? "text-pass" : "text-fail"}`}>
                    {best.delta.l_net <= 0 ? "giảm" : "tăng"} {formatVnd(Math.abs(best.delta.l_net))} so với bộ luật hiện hành
                  </span>
                )}
              </p>
            </div>
            <button
              type="button"
              data-tour="changeset"
              onClick={() => proposeChangeSet(data!.variants.indexOf(best))}
              disabled={running}
              className="btn btn-primary btn-lg"
            >
              Tạo change set cho phương án này
            </button>
          </div>
        )}
        {data && <ResultsTable uid={uid} rows={rows} />}
        {data && <LnetStackedBar rows={chartRows} />}
        {data && <ScenarioTable uid={uid} rows={rows} />}
      </section>
    </div>
  );
}

/** Nhóm radio dạng nút phân đoạn: radio gốc vẫn nhận bàn phím (mũi tên), nhãn đang chọn nổi lên + in đậm. */
function Segmented<T extends string | number>({
  caption,
  label,
  name,
  options,
  value,
  onChange,
}: {
  caption: string;
  label: string;
  name: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div>
      <p aria-hidden className="label mb-1">
        {caption}
      </p>
      <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-lg border border-line bg-sunken p-0.5">
        {options.map((o) => (
          <label
            key={String(o.value)}
            className="inline-flex min-h-10 cursor-pointer items-center rounded-md px-3 text-sm text-muted hover:text-foreground has-[:checked]:bg-surface has-[:checked]:font-semibold has-[:checked]:text-foreground has-[:checked]:shadow-sm has-[:checked]:ring-1 has-[:checked]:ring-line-strong has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-accent pointer-coarse:min-h-11"
          >
            <input type="radio" name={name} className="sr-only" checked={value === o.value} onChange={() => onChange(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </div>
  );
}

type Row = { name: string; r: BacktestResult; rank?: number; eligible: boolean; verdict?: string; errors?: string[] };

function ResultsTable({ uid, rows }: { uid: string; rows: Row[] }) {
  const exposure = (r: BacktestResult) => r.compliance_exposure.reduce((n, e) => n + e.count, 0);
  return (
    <div tabIndex={0} role="region" aria-labelledby={`${uid}-cmp-cap`} data-tour="results" className="table-wrap">
      <table className="data-table min-w-[860px]">
        <caption id={`${uid}-cmp-cap`}>
          L_net = lọt gian lận + chi phí duyệt + mất do khách bỏ (đ, làm tròn xuống theo nhóm). Hàng in đậm là phương án tốt nhất.
        </caption>
        <thead>
          <tr>
            <th scope="col" className="sticky-col min-w-40">Phương án</th>
            <th scope="col" className="n">L_net</th>
            <th scope="col" className="n">Lọt gian lận</th>
            <th scope="col" className="n">Chặn nhầm (giữ / chặn)</th>
            <th scope="col" className="n">Chi phí duyệt</th>
            <th scope="col" className="n">Mất do khách bỏ</th>
            <th scope="col" className="n">Dòng tiền mule bị giữ/chặn</th>
            <th scope="col">Cổng invariant</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const top = row.rank === 1;
            const exp = exposure(row.r);
            const cell = top ? "bg-accent-soft" : "";
            return (
              <tr key={row.name} className={top ? "font-semibold" : undefined}>
                <th scope="row" className={`sticky-col text-left ${top ? "bg-accent-soft!" : ""}`}>
                  <span className="block">{row.name}</span>
                  {top && <span className="mt-1 inline-block text-xs font-semibold text-accent">Tốt nhất · hạng 1</span>}
                  {!top && row.rank && <span className="mt-0.5 block text-xs font-normal text-muted">Hạng {row.rank}</span>}
                  {i === 0 && <span className="mt-0.5 block text-xs font-normal text-muted">Mốc so sánh</span>}
                </th>
                <td className={`n text-[0.9375rem] ${cell} ${top ? "font-bold" : "font-medium"}`}>{formatVnd(row.r.l_net)}</td>
                <td className={`n ${cell}`}>{formatVnd(row.r.fn_loss)}</td>
                <td className={`n ${cell}`}>
                  {formatInt(row.r.fp_hold)} / {formatInt(row.r.fp_block)}
                </td>
                <td className={`n ${cell}`}>{formatVnd(row.r.review_cost)}</td>
                <td className={`n ${cell}`}>{formatVnd(row.r.churn_loss)}</td>
                <td className={`n ${cell}`}>{formatVnd(row.r.mule_flow_stopped)}</td>
                <td className={`${cell} whitespace-nowrap`}>
                  {i === 0 ? (
                    <span className="text-xs font-normal text-muted">—</span>
                  ) : row.eligible ? (
                    <VerdictBadge verdict={(row.verdict as "PASS") ?? "PASS"} />
                  ) : (
                    <span className="chip tone-fail font-semibold">
                      Không hợp lệ{exp > 0 ? ` · ${formatInt(exp)} giao dịch phạm tuân thủ` : ""}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ScenarioTable({ uid, rows }: { uid: string; rows: Row[] }) {
  const scenarios = SCENARIO_ORDER.filter((s) => rows[0]?.r.by_scenario[s]);
  return (
    <div tabIndex={0} role="region" aria-labelledby={`${uid}-sc-cap`} data-tour="scenarios" className="table-wrap">
      <table className="data-table min-w-[760px]">
        <caption id={`${uid}-sc-cap`} className="font-semibold text-foreground!">
          Phân rã theo kịch bản: lọt gian lận và số giao dịch thật bị giữ/chặn nhầm
        </caption>
        <thead>
          <tr>
            <th scope="col" className="sticky-col">Kịch bản</th>
            {rows.map((row, i) => (
              <th key={row.name} scope="col" className="n">
                {i === 0 ? "Hiện hành" : row.name.split(" · ")[0]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {scenarios.map((sc) => (
            <tr key={sc}>
              <th scope="row" className="sticky-col text-left font-medium">
                {rows[0].r.by_scenario[sc].label_vi}
              </th>
              {rows.map((row) => {
                const m = row.r.by_scenario[sc];
                const fp = m.fp_hold + m.fp_block;
                return (
                  <td key={row.name} className="n">
                    {m.loss_total > 0 && <span className="block">Lọt {formatVnd(m.fn_loss)}</span>}
                    <span className={`block ${fp > 0 ? "font-semibold text-warn" : "text-muted"}`}>Chặn nhầm {formatInt(fp)}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
