/** Nhãn nguồn của nội dung (docs/07 mục 1): AI đề xuất, người viết, hệ thống tính, sửa tự động. Chữ nhỏ, không trang trí. */
export type Source = "ai" | "cache" | "human" | "system" | "det";

const LABEL: Record<Source, string> = {
  ai: "AI đề xuất",
  cache: "AI · kết quả đã lưu",
  human: "Người viết",
  system: "Hệ thống tính",
  det: "Sửa tự động (không dùng AI)",
};

export function SourceTag({ source, label, className = "" }: { source: Source; label?: string; className?: string }) {
  const ai = source === "ai" || source === "cache";
  return (
    <span
      className={`inline-flex items-center rounded-[3px] border px-1.5 text-xs leading-5 font-medium ${
        ai ? "border-accent-line text-accent" : "border-line text-muted"
      } ${className}`}
    >
      {label ?? LABEL[source]}
    </span>
  );
}
