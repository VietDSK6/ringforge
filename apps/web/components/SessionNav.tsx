"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Icon, type IconName } from "@/components/Icon";
import { api } from "@/lib/api";

const ITEMS: { href: string; label: string; short: string; icon: IconName }[] = [
  { href: "policies", label: "Bộ luật", short: "Bộ luật", icon: "rules" },
  { href: "studio", label: "Rule Studio", short: "Studio", icon: "studio" },
  { href: "compare", label: "So sánh", short: "So sánh", icon: "compare" },
  { href: "pack", label: "Policy Pack", short: "Pack", icon: "pack" },
  { href: "review", label: "Duyệt", short: "Duyệt", icon: "review" },
];

/** Thanh bên trái (desktop) / thanh dưới (mobile). Đây là điều hướng trang, không phải tab ARIA. */
export function SessionNav() {
  const { sid } = useParams<{ sid: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const [resetting, setResetting] = useState(false);

  async function reset() {
    if (!window.confirm("Đưa sandbox về trạng thái ban đầu? Mọi luật bạn đã thêm trong phiên này sẽ mất.")) return;
    setResetting(true);
    try {
      await api.resetSession(sid);
      router.push(`/s/${sid}/policies`);
      router.refresh();
    } finally {
      setResetting(false);
    }
  }

  return (
    <nav
      aria-label="Điều hướng sandbox"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:sticky md:top-12 md:z-auto md:h-fit md:w-52 md:shrink-0 md:border-0 md:bg-transparent md:pb-0"
    >
      <ul className="flex md:flex-col md:gap-0.5">
        {ITEMS.map((it) => {
          const href = `/s/${sid}/${it.href}`;
          const active = pathname.startsWith(href);
          return (
            <li key={it.href} className="flex-1">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-14 flex-col items-center justify-center gap-1 px-1 text-xs md:min-h-10 md:flex-row md:justify-start md:gap-2.5 md:rounded-md md:px-3 md:text-sm ${
                  active
                    ? "font-semibold text-foreground md:bg-surface md:ring-1 md:ring-line"
                    : "text-muted hover:text-foreground md:hover:bg-sunken"
                }`}
              >
                {/* Vạch chỉ báo trang hiện tại: không chỉ dựa vào màu. */}
                {active && (
                  <span
                    aria-hidden
                    className="absolute inset-x-3 top-0 h-0.5 bg-foreground md:hidden"
                  />
                )}
                <Icon name={it.icon} className="size-5 md:size-4" />
                <span className="md:hidden">{it.short}</span>
                <span className="hidden md:inline">{it.label}</span>
              </Link>
            </li>
          );
        })}
        <li className="flex-1 md:mt-3 md:border-t md:border-line md:pt-3">
          <button
            type="button"
            onClick={reset}
            disabled={resetting}
            className="flex min-h-14 w-full flex-col items-center justify-center gap-1 px-1 text-xs text-muted hover:text-foreground disabled:opacity-50 md:min-h-10 md:flex-row md:justify-start md:gap-2.5 md:rounded-md md:px-3 md:text-sm md:hover:bg-sunken"
          >
            <Icon name="reset" className="size-5 md:size-4" />
            <span className="md:hidden">{resetting ? "Đang reset…" : "Reset"}</span>
            <span className="hidden md:inline">{resetting ? "Đang reset…" : "Reset sandbox"}</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
