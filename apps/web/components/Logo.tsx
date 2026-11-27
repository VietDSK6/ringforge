import Link from "next/link";

/** Logo chữ: không dùng biểu tượng trang trí. */
export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex min-h-11 items-center rounded-md text-[1.0625rem] font-bold tracking-[-0.01em]">
      RingForge
    </Link>
  );
}
