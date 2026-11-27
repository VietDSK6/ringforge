import type { ReactNode } from "react";

import { Icon, type IconName } from "@/components/Icon";

type Tone = "warn" | "fail" | "pass" | "info";

const TONE: Record<Tone, { icon: IconName; cls: string }> = {
  warn: { icon: "alert", cls: "border-warn-line bg-warn-soft" },
  fail: { icon: "x", cls: "border-fail-line bg-fail-soft" },
  pass: { icon: "check", cls: "border-pass-line bg-pass-soft" },
  info: { icon: "help", cls: "border-line bg-sunken" },
};
const ICON_CLS: Record<Tone, string> = { warn: "text-warn", fail: "text-fail", pass: "text-pass", info: "text-muted" };

/** Hộp thông báo có biểu tượng + màu ngữ nghĩa (lỗi, cảnh báo, dự phòng AI). */
export function Callout({
  tone,
  title,
  children,
  role,
  className = "",
  id,
}: {
  tone: Tone;
  title?: ReactNode;
  children?: ReactNode;
  role?: "alert" | "status";
  className?: string;
  id?: string;
}) {
  const t = TONE[tone];
  return (
    <div id={id} role={role} className={`flex gap-3 rounded-lg border px-3.5 py-3 text-sm leading-6 ${t.cls} ${className}`}>
      <span className={`mt-1 ${ICON_CLS[tone]}`}>
        <Icon name={t.icon} />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  );
}
