import type { ReactNode } from "react";

/*
 * Bộ biểu tượng RingForge, vẽ tay trên lưới 24×24:
 * - nét 1,5 px, đầu và góc nối tròn, không tô (trừ chấm nhỏ ≤ 1,2 px);
 * - vùng an toàn 3 px mỗi cạnh (hình nằm trong ô 18×18), bo góc hình chữ nhật 2 px;
 * - hình học đơn giản để đọc rõ ở 16 px. Luôn trang trí: aria-hidden.
 */
const GLYPHS = {
  // Bộ luật: danh sách có chấm đầu dòng.
  rules: (
    <>
      <path d="M9.5 6.5h10M9.5 12h10M9.5 17.5h10" />
      <circle cx="5" cy="6.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="5" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="5" cy="17.5" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  // Rule Studio: bút viết.
  studio: (
    <>
      <path d="M4.5 19.5l.9-3.9L15.6 5.4a2 2 0 0 1 2.83 0l.17.17a2 2 0 0 1 0 2.83L8.4 18.6l-3.9.9z" />
      <path d="M13.5 7.5l3 3" />
    </>
  ),
  // So sánh: ba cột cao thấp khác nhau.
  compare: (
    <>
      <rect x="4.25" y="11.5" width="3.75" height="8" rx="1" />
      <rect x="10.125" y="4.5" width="3.75" height="15" rx="1" />
      <rect x="16" y="8.5" width="3.75" height="11" rx="1" />
    </>
  ),
  // Policy Pack: văn bản quy định (góc gấp).
  pack: (
    <>
      <path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z" />
      <path d="M13.5 3.5V9H19" />
      <path d="M8.5 13h7M8.5 16.5h4.5" />
    </>
  ),
  // Duyệt: hộp có dấu kiểm.
  review: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M8.5 12.25l2.5 2.5 4.75-5.25" />
    </>
  ),
  // Reset: mũi tên quay ngược.
  reset: (
    <>
      <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3L4.5 9" />
      <path d="M4.5 4.5V9H9" />
    </>
  ),
  // Mở/đóng chi tiết.
  chevron: <path d="M9.5 6l6 6-6 6" />,
  // Luật pháp lý bị khóa.
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="9.5" rx="2" />
      <path d="M8.5 10.5V7.75a3.5 3.5 0 0 1 7 0v2.75" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  alert: (
    <>
      <path d="M10.27 4.5a2 2 0 0 1 3.46 0l6.93 12a2 2 0 0 1-1.73 3H5.07a2 2 0 0 1-1.73-3z" />
      <path d="M12 9.5v4" />
      <circle cx="12" cy="16.5" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
  x: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof GLYPHS;

/** className thay toàn bộ lớp mặc định: luôn kèm kích thước (size-*). */
export function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      className={`shrink-0 ${className}`}
    >
      {GLYPHS[name]}
    </svg>
  );
}
