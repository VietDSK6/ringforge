import Link from "next/link";

/** Dấu hiệu RingForge: một vòng (ring) khép kín bởi một nét kiểm (đã kiểm chứng). */
export function LogoMark({ className = "size-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden focusable="false" className={className}>
      <rect width="24" height="24" rx="6" fill="var(--accent)" />
      <circle cx="12" cy="12" r="6.25" fill="none" stroke="var(--accent-fg)" strokeWidth="2" strokeDasharray="30 9.3" transform="rotate(-50 12 12)" />
      <path d="M9.4 12.1l1.9 1.9 3.4-3.7" fill="none" stroke="var(--accent-fg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex min-h-11 items-center gap-2.5 rounded-md text-[1.0625rem] font-bold tracking-tight">
      <LogoMark />
      RingForge
    </Link>
  );
}
