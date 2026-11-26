// Định dạng hiển thị tiếng Việt. Tiền: "10.000.000 đ" (Intl vi-VN, số nguyên).
import type { AuthLevel, CatalogField, Decision, RuleKind, RuleStatus } from "./types";

const intFmt = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

export const formatInt = (n: number) => intFmt.format(n);
export const formatVnd = (n: number) => `${intFmt.format(n)} đ`;

export const KIND_VI: Record<RuleKind, string> = { REGULATORY: "Pháp lý", FRAUD: "Gian lận", FRICTION: "Ma sát" };
export const STATUS_VI: Record<RuleStatus, string> = {
  ACTIVE: "Đang chạy",
  CANDIDATE: "Ứng viên",
  SHADOW: "Shadow",
  RETIRED: "Đã ngừng",
};
export const DECISION_VI: Record<Decision, string> = {
  ALLOW: "Cho qua",
  MONITOR: "Cho qua + giám sát",
  HOLD: "Giữ lại để xác minh",
  BLOCK: "Chặn",
};
export const AUTH_VI: Record<AuthLevel, string> = {
  NONE: "không xác thực thêm",
  OTP: "OTP",
  BIOMETRIC: "sinh trắc học",
};

/** Giá trị một trường của giao dịch theo đơn vị trong catalog. */
export function formatFieldValue(field: CatalogField | undefined, value: number | boolean | string): string {
  if (!field) return String(value);
  if (field.type === "bool") return value ? "có" : "không";
  if (field.type === "enum") return field.value_labels_vi?.[String(value)] ?? String(value);
  const n = Number(value);
  switch (field.unit) {
    case "VND":
      return formatVnd(n);
    case "giờ":
      return `${String(n).padStart(2, "0")}:00`;
    case "%":
      return `${formatInt(n)}%`;
    case "ngày":
      return `${formatInt(n)} ngày`;
    default:
      return formatInt(n);
  }
}
