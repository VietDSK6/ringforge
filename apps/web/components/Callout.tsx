import type { ReactNode } from "react";

type Tone = "warn" | "fail" | "pass" | "info";

const TONE: Record<Tone, string> = {
  warn: "border-warn-line bg-warn-soft",
  fail: "border-fail-line bg-fail-soft",
  pass: "border-pass-line bg-pass-soft",
  info: "border-line bg-sunken",
};
const TITLE: Record<Tone, string> = { warn: "text-warn", fail: "text-fail", pass: "text-pass", info: "text-foreground" };

/** Hộp thông báo (lỗi, cảnh báo, dự phòng AI): nền nhạt + viền mảnh theo màu ngữ nghĩa. */
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
  return (
    <div id={id} role={role} className={`space-y-1 rounded-md border px-3.5 py-2.5 text-sm leading-6 ${TONE[tone]} ${className}`}>
      {title && <p className={`font-semibold ${TITLE[tone]}`}>{title}</p>}
      {children}
    </div>
  );
}
