import { Icon, type IconName } from "@/components/Icon";

/** Nhãn nguồn của nội dung (docs/07 mục 1): AI đề xuất, người viết, hệ thống tính, sửa tất định. */
export type Source = "ai" | "cache" | "human" | "system" | "det";

const STYLE: Record<Source, { icon: IconName; label: string; cls: string }> = {
  ai: { icon: "spark", label: "AI đề xuất", cls: "tone-accent" },
  cache: { icon: "spark", label: "AI · kết quả đã lưu", cls: "tone-accent" },
  human: { icon: "user", label: "Người viết", cls: "" },
  system: { icon: "cpu", label: "Hệ thống tính", cls: "" },
  det: { icon: "cpu", label: "Tất định", cls: "" },
};

export function SourceTag({ source, label, className = "" }: { source: Source; label?: string; className?: string }) {
  const s = STYLE[source];
  return (
    <span className={`chip ${s.cls} ${s.cls ? "" : "text-muted"} ${className}`}>
      <Icon name={s.icon} className="size-3.5" />
      {label ?? s.label}
    </span>
  );
}
