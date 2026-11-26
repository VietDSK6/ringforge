import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, { icon: string; label: string; cls: string }> = {
  PASS: { icon: "✅", label: "Đạt", cls: "bg-emerald-50 text-ok ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-900" },
  PASS_WITH_WARNINGS: { icon: "⚠️", label: "Đạt có cảnh báo", cls: "bg-amber-50 text-warn ring-amber-200 dark:bg-amber-950 dark:ring-amber-900" },
  FAIL: { icon: "❌", label: "Không đạt", cls: "bg-red-50 text-danger ring-red-200 dark:bg-red-950 dark:ring-red-900" },
  UNKNOWN: { icon: "❔", label: "Không kết luận được", cls: "bg-zinc-100 text-muted ring-zinc-300 dark:bg-zinc-900 dark:ring-zinc-700" },
};

export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  const s = STYLE[verdict];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full font-semibold ring-1 ${s.cls} ${large ? "px-4 py-2 text-lg" : "px-2.5 py-0.5 text-sm"}`}
    >
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  );
}
