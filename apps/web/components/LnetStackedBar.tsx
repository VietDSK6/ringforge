"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, type TooltipContentProps, XAxis, YAxis } from "recharts";

import { formatVnd } from "@/lib/format";

export interface LnetRow {
  label: string;
  fn_loss: number;
  review_cost: number;
  churn_loss: number;
  l_net: number;
}

// Thứ tự cố định: màu đi theo thành phần, không theo hạng (dataviz).
const SERIES = [
  { key: "fn_loss", name: "Lọt gian lận", color: "var(--series-1)" },
  { key: "review_cost", name: "Chi phí duyệt", color: "var(--series-2)" },
  { key: "churn_loss", name: "Mất do khách bỏ", color: "var(--series-3)" },
] as const;

const compactVnd = (n: number) =>
  n === 0
    ? "0"
    : n >= 1e9
      ? `${(n / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`
      : `${Math.round(n / 1e6).toLocaleString("vi-VN")} tr`;

function ChartTooltip({ active, payload, label }: Partial<TooltipContentProps<number, string>>) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as LnetRow;
  return (
    <div className="min-w-60 rounded-lg border border-line bg-surface p-3 text-[0.8125rem] shadow-pop">
      <p className="font-semibold">{label}</p>
      <dl className="mt-2 space-y-1">
        {SERIES.map((s) => (
          <div key={s.key} className="flex items-center justify-between gap-4">
            <dt className="flex items-center gap-2 text-muted">
              <span aria-hidden className="size-2.5 rounded-sm" style={{ background: s.color }} />
              {s.name}
            </dt>
            <dd className="num">{formatVnd(row[s.key])}</dd>
          </div>
        ))}
        <div className="mt-1 flex justify-between gap-4 border-t border-line pt-1.5 font-semibold">
          <dt>L_net</dt>
          <dd className="num">{formatVnd(row.l_net)}</dd>
        </div>
      </dl>
    </div>
  );
}

/** Thành phần L_net theo phương án, cột ngang chồng (docs/07 mục 3.5). Bảng số bên trên là bản thay thế dạng bảng. */
export function LnetStackedBar({ rows }: { rows: LnetRow[] }) {
  const height = 52 * rows.length + 48;
  return (
    <figure className="panel space-y-3 p-4 sm:p-5">
      <figcaption className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <span className="max-w-[60ch] text-sm text-muted">
          Thành phần tổn thất ròng L_net theo phương án (đ, trên 6 ngày dữ liệu tổng hợp). Số chính xác ở bảng phía trên.
        </span>
        {/* Chú thích tự dựng: thứ tự cố định theo thành phần, đọc được bằng trình đọc màn hình. */}
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem]" aria-label="Chú thích màu">
          {SERIES.map((s) => (
            <li key={s.key} className="inline-flex items-center gap-2">
              <span aria-hidden className="size-3 rounded-sm" style={{ background: s.color }} />
              {s.name}
            </li>
          ))}
        </ul>
      </figcaption>
      <div role="img" aria-label="Biểu đồ cột chồng thành phần L_net theo phương án; số liệu chi tiết có trong bảng so sánh.">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 0 }} barCategoryGap={12}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis
              type="number"
              tickFormatter={compactVnd}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              tickMargin={6}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={156}
              tick={{ fill: "var(--foreground)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border-strong)" }}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: "var(--sunken)" }} content={<ChartTooltip />} />
            {SERIES.map((s, i) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                stackId="lnet"
                fill={s.color}
                stroke="var(--surface)"
                strokeWidth={1.5}
                radius={i === SERIES.length - 1 ? [0, 3, 3, 0] : 0}
                maxBarSize={26}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
