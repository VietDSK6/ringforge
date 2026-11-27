import { Icon, type IconName } from "@/components/Icon";
import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, { icon: IconName; label: string; tone: string }> = {
  PASS: { icon: "check", label: "Đạt", tone: "tone-pass" },
  PASS_WITH_WARNINGS: { icon: "alert", label: "Đạt có cảnh báo", tone: "tone-warn" },
  FAIL: { icon: "x", label: "Không đạt", tone: "tone-fail" },
  UNKNOWN: { icon: "help", label: "Không kết luận được", tone: "tone-unknown" },
};

export const VERDICT_TONE: Record<Verdict, "pass" | "warn" | "fail" | "unknown"> = {
  PASS: "pass",
  PASS_WITH_WARNINGS: "warn",
  FAIL: "fail",
  UNKNOWN: "unknown",
};

export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  const s = STYLE[verdict];
  return (
    <span
      className={`inline-flex items-center rounded-full border font-semibold whitespace-nowrap ${s.tone} ${
        large ? "gap-2 px-3.5 py-1.5 text-base" : "gap-1.5 px-2.5 py-0.5 text-[0.8125rem] leading-5"
      }`}
    >
      <Icon name={s.icon} className={large ? "size-5" : "size-3.5"} />
      {s.label}
    </span>
  );
}
