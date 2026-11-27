import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, { label: string; tone: string; glyph: string }> = {
  PASS: { label: "Đạt", tone: "text-pass", glyph: "✓" },
  PASS_WITH_WARNINGS: { label: "Đạt có cảnh báo", tone: "text-warn", glyph: "!" },
  FAIL: { label: "Không đạt", tone: "text-fail", glyph: "✕" },
  UNKNOWN: { label: "Không kết luận được", tone: "text-unknown", glyph: "?" },
};

export const VERDICT_TONE: Record<Verdict, "pass" | "warn" | "fail" | "unknown"> = {
  PASS: "pass",
  PASS_WITH_WARNINGS: "warn",
  FAIL: "fail",
  UNKNOWN: "unknown",
};

/** Kết luận kiểm chứng: ký hiệu trong ô vuông đặc + chữ, cùng màu ngữ nghĩa (không dựa vào màu: chữ và ký hiệu mang nghĩa). */
export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  const s = STYLE[verdict];
  return (
    <span className={`inline-flex items-center font-semibold whitespace-nowrap ${s.tone} ${large ? "gap-2.5 text-xl" : "gap-1.5 text-[0.8125rem] leading-5"}`}>
      <span
        aria-hidden
        className={`inline-flex items-center justify-center rounded-[3px] bg-current ${large ? "size-6" : "size-4"}`}
      >
        <span className={`font-bold text-surface ${large ? "text-[0.8125rem]" : "text-[0.625rem]"}`}>{s.glyph}</span>
      </span>
      {s.label}
    </span>
  );
}
