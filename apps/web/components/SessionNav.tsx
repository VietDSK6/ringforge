"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

const ITEMS = [
  { href: "policies", label: "Bộ luật", icon: "📋" },
  { href: "studio", label: "Rule Studio", icon: "✍️" },
  { href: "pack", label: "Policy Pack", icon: "⚖️" },
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
      className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-surface md:sticky md:top-8 md:h-fit md:w-52 md:shrink-0 md:rounded-2xl md:border"
    >
      <ul className="flex md:flex-col md:p-2">
        {ITEMS.map((it) => {
          const href = `/s/${sid}/${it.href}`;
          const active = pathname.startsWith(href);
          return (
            <li key={it.href} className="flex-1">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-xl px-3 py-2 text-xs md:flex-row md:justify-start md:gap-2 md:text-sm ${
                  active ? "bg-violet-50 font-semibold text-accent dark:bg-violet-950" : "hover:bg-background"
                }`}
              >
                <span aria-hidden>{it.icon}</span>
                {it.label}
              </Link>
            </li>
          );
        })}
        <li className="flex-1 md:mt-2 md:border-t md:border-line md:pt-2">
          <button
            type="button"
            onClick={reset}
            disabled={resetting}
            className="flex min-h-12 w-full flex-col items-center justify-center gap-0.5 rounded-xl px-3 py-2 text-xs text-muted hover:bg-background disabled:opacity-50 md:flex-row md:justify-start md:gap-2 md:text-sm"
          >
            <span aria-hidden>↺</span>
            {resetting ? "Đang reset…" : "Reset sandbox"}
          </button>
        </li>
      </ul>
    </nav>
  );
}
