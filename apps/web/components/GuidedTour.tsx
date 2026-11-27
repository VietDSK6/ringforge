"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";

export interface TourStep {
  /** Giá trị thuộc tính data-tour của phần tử cần chỉ vào. */
  target: string;
  /** Một câu, tối đa 15 từ (docs/07 mục 4). */
  text: string;
  /** "click": tự sang bước sau khi người dùng bấm vào phần tử đó. */
  advanceOn?: "click";
  /** Gợi ý khi phần tử chưa xuất hiện (ví dụ cần bấm nút ở bước trước). */
  waiting?: string;
}

type Rect = { top: number; left: number; width: number; height: number };

const PANEL_W = 320;
const GAP = 12;
const storageKey = (id: string) => `rf.tour.${id}`;

function wasDismissed(id: string): boolean {
  try {
    return localStorage.getItem(storageKey(id)) === "done";
  } catch {
    return false;
  }
}

function remember(id: string) {
  try {
    localStorage.setItem(storageKey(id), "done");
  } catch {
    /* chế độ riêng tư / bị chặn lưu trữ: chỉ là tiện ích */
  }
}

/** Hướng dẫn từng bước cho một demo (FR-S3). Không chặn trang: người dùng vẫn thao tác bình thường. */
export function GuidedTour({ id, steps, enabled }: { id: string; steps: TourStep[]; enabled: boolean }) {
  const uid = useId();
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);
  const [panelH, setPanelH] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const step = steps[index];

  useEffect(() => {
    // Mở sau khi gắn vào DOM để không lệch với HTML dựng sẵn (localStorage chỉ có ở trình duyệt).
    const t = setTimeout(() => setOpen(enabled && !wasDismissed(id)), 0);
    return () => clearTimeout(t);
  }, [enabled, id]);

  const close = useCallback(() => {
    remember(id);
    setOpen(false);
  }, [id]);

  const next = useCallback(() => {
    if (index + 1 >= steps.length) close();
    else setIndex((i) => i + 1);
  }, [index, steps.length, close]);

  // Theo dõi phần tử đích: chờ nó xuất hiện, cuộn tới, cập nhật vị trí khi cuộn/đổi kích thước.
  useEffect(() => {
    if (!open || !step) return;
    let el: Element | null = null;
    let frame = 0;
    let scrolled = false;
    const measure = () => {
      el = document.querySelector(`[data-tour="${step.target}"]`);
      if (!el) {
        setRect(null);
        return;
      }
      if (!scrolled) {
        scrolled = true;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
      }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      setPanelH(dialogRef.current?.offsetHeight ?? 0);
    };
    const onChange = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    // Đo lại định kỳ: bố cục có thể xê dịch mà không có sự kiện cuộn (banner, kết quả mới chèn vào).
    const poll = setInterval(onChange, 400);
    onChange();
    window.addEventListener("scroll", onChange, true);
    window.addEventListener("resize", onChange);
    return () => {
      clearInterval(poll);
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onChange, true);
      window.removeEventListener("resize", onChange);
    };
  }, [open, step]);

  // Bước "click": bấm vào phần tử đích thì tự sang bước sau.
  useEffect(() => {
    if (!open || step?.advanceOn !== "click") return;
    const onClick = (e: MouseEvent) => {
      const target = (e.target as Element | null)?.closest(`[data-tour="${step.target}"]`);
      if (target) setTimeout(next, 150);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [open, step, next]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  useLayoutEffect(() => {
    const d = dialogRef.current;
    if (!d) return;
    if (open && !d.open) d.show(); // không modal: trang vẫn dùng được
    if (!open && d.open) d.close();
  }, [open]);

  if (!step) return null;

  // Đặt khung hướng dẫn dưới phần tử đích, thiếu chỗ thì đặt phía trên; màn hẹp thì ghim đáy màn hình.
  const vw = typeof window === "undefined" ? 1024 : window.innerWidth;
  const vh = typeof window === "undefined" ? 768 : window.innerHeight;
  const narrow = vw < 640;
  // Chưa mở (kể cả lúc hydrate) thì không tính theo cửa sổ: HTML server và client khớp nhau.
  let style: React.CSSProperties;
  if (!open) {
    style = {};
  } else if (narrow || !rect) {
    style = { left: 16, right: 16, bottom: narrow ? 88 : 24, width: "auto" };
  } else {
    const h = panelH || 180;
    const below = rect.top + rect.height + GAP;
    const top = below + h < vh ? below : Math.max(16, rect.top - GAP - h);
    const left = Math.min(Math.max(16, rect.left), vw - PANEL_W - 16);
    style = { top, left, width: PANEL_W };
  }

  return (
    <>
      {open && rect && (
        <div
          aria-hidden
          className="pointer-events-none fixed z-40 rounded-lg ring-2 ring-accent ring-offset-2 ring-offset-background"
          style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }}
        />
      )}
      <dialog
        ref={dialogRef}
        aria-labelledby={`${uid}-text`}
        className="fixed z-50 m-0 rounded-xl border border-line bg-surface p-4 text-foreground shadow-pop"
        style={style}
      >
        <div className="flex items-center justify-between gap-3">
          <p className="num text-xs text-muted">
            Hướng dẫn · bước {index + 1}/{steps.length}
          </p>
          <span aria-hidden className="flex gap-1">
            {steps.map((_, i) => (
              <span key={i} className={`h-1 w-4 rounded-full ${i <= index ? "bg-accent" : "bg-line"}`} />
            ))}
          </span>
        </div>
        <p id={`${uid}-text`} className="mt-2 font-medium leading-6">
          {step.text}
        </p>
        {!rect && step.waiting && (
          <p className="mt-1 flex items-center gap-2 text-sm text-muted">
            <span aria-hidden className="size-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            {step.waiting}
          </p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {index > 0 && (
            <button type="button" onClick={() => setIndex((i) => i - 1)} className="btn btn-secondary btn-sm">
              Quay lại
            </button>
          )}
          <button type="button" onClick={next} className="btn btn-primary btn-sm">
            {index + 1 >= steps.length ? "Xong" : "Tiếp"}
          </button>
          <button type="button" onClick={close} className="btn btn-ghost btn-sm ml-auto underline underline-offset-2">
            Bỏ qua hướng dẫn
          </button>
        </div>
      </dialog>
    </>
  );
}
