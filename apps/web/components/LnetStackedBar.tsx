"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
  n >= 1e9 ? `${(n / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ` : `${Math.round(n / 1e6).toLocaleString("vi-VN")} tr`;

/** Thành phần L_net theo phương án, cột ngang chồng (docs/07 mục 3.5). Bảng số bên trên là bản thay thế dạng bảng. */
export function LnetStackedBar({ rows }: { rows: LnetRow[] }) {
  const height = 56 * rows.length + 90;
  return (
    <figure className="space-y-2">
      <figcaption className="text-sm text-muted">
        Thành phần tổn thất ròng L_net theo phương án (đ, trên 6 ngày dữ liệu tổng hợp). Số chính xác ở bảng phía trên.
      </figcaption>
      <div role="img" aria-label="Biểu đồ cột chồng thành phần L_net theo phương án; số liệu chi tiết có trong bảng so sánh.">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barCategoryGap={14}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis
              type="number"
              tickFormatter={compactVnd}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={118}
              tick={{ fill: "var(--foreground)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "var(--border)", opacity: 0.4 }}
              itemSorter={(item) => SERIES.findIndex((s) => s.key === item.dataKey)}
              formatter={(value, name) => [formatVnd(Number(value)), String(name)]}
              labelFormatter={(label, payload) => {
                const total = payload?.[0]?.payload?.l_net;
                return total === undefined ? String(label) : `${label} · L_net ${formatVnd(total)}`;
              }}
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                color: "var(--foreground)",
                fontSize: 13,
              }}
              labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
              itemStyle={{ color: "var(--foreground)" }}
            />
            <Legend itemSorter={null} wrapperStyle={{ fontSize: 13, color: "var(--foreground)" }} />
            {SERIES.map((s, i) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                stackId="lnet"
                fill={s.color}
                stroke="var(--surface)"
                strokeWidth={2}
                radius={i === SERIES.length - 1 ? [0, 4, 4, 0] : 0}
                maxBarSize={28}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
