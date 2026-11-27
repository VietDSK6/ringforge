/** Biểu tượng nét mảnh vẽ tay (SVG nội tuyến, không dùng thư viện). Luôn trang trí: aria-hidden. */
const PATHS = {
  check: "M4.5 10.5l3.5 3.5 7.5-8",
  x: "M5.5 5.5l9 9m0-9l-9 9",
  alert: "M10 3.5l7 12.5H3L10 3.5zM10 8.5v3.5M10 14.2v.1",
  help: "M10 17.5a7.5 7.5 0 100-15 7.5 7.5 0 000 15zM7.8 7.9a2.3 2.3 0 114.1 1.4c-.7.8-1.9 1.2-1.9 2.4M10 14.2v.1",
  rules: "M6.5 5h10M6.5 10h10M6.5 15h10M3.5 5h.1M3.5 10h.1M3.5 15h.1",
  studio: "M4 16l1-4 8.5-8.5a2.1 2.1 0 013 3L8 15l-4 1zM12 5l3 3",
  compare: "M4 16V9M8.5 16V4M13 16v-5M17 16V7M2.5 16.5h15",
  scale: "M10 3.5v13M5.5 16.5h9M4 6.5h12M4 6.5L2 11a2.5 2.5 0 004 0L4 6.5zm12 0L14 11a2.5 2.5 0 004 0l-2-4.5z",
  review: "M7 10l2 2 4-4.5M10 17.5a7.5 7.5 0 100-15 7.5 7.5 0 000 15z",
  reset: "M3.5 10a6.5 6.5 0 106.5-6.5c-2 0-3.8.9-5 2.4M4 3v3.5h3.5",
  lock: "M5.5 9V7a4.5 4.5 0 019 0v2M4.5 9h11v8h-11V9z",
  spark: "M10 2.5l1.6 4.4 4.4 1.6-4.4 1.6L10 14.5l-1.6-4.4L4 8.5l4.4-1.6L10 2.5zM15.5 13.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z",
  cpu: "M6 6h8v8H6V6zM8 2.5V6m4-3.5V6M8 14v3.5m4-3.5v3.5M2.5 8H6m-3.5 4H6m8-4h3.5M14 12h3.5",
  user: "M10 9.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM3.5 17.5c.8-3 3.4-5 6.5-5s5.7 2 6.5 5",
  shield: "M10 2.5l6 2.5v4.5c0 3.8-2.6 6.6-6 8-3.4-1.4-6-4.2-6-8V5l6-2.5z",
  arrow: "M4 10h12m-4.5-4.5L16 10l-4.5 4.5",
  plus: "M10 4v12M4 10h12",
  download: "M10 3v10m-4-4l4 4 4-4M3.5 16.5h13",
  upload: "M10 13V3M6 7l4-4 4 4M3.5 16.5h13",
  flag: "M5 17.5V3m0 1h9l-2 3.5 2 3.5H5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
