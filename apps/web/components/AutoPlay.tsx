"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import type { VerifyReport } from "@/lib/types";

/**
 * "Xem demo 60 giây": tự chạy Demo 1 như một người dùng (gõ câu, bấm Biên dịch, Kiểm chứng, Sửa bằng AI) kèm lời dẫn.
 * Chỉ bấm các nút có sẵn trên trang (qua data-tour), không gọi API riêng; mọi kết quả vẫn do hệ thống tính.
 * Lời dẫn không chứa con số: số liệu nằm trên màn hình, đọc từ kết quả thật.
 */
export function AutoPlay({
  enabled,
  sid,
  texts,
  setText,
  report,
}: {
  enabled: boolean;
  sid: string;
  texts: [string, string];
  setText: (s: string) => void;
  report: VerifyReport | null;
}) {
  const [caption, setCaption] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const stopped = useRef(false);
  const reportRef = useRef(report);
  useEffect(() => {
    reportRef.current = report;
  }, [report]);
  const TOTAL = 7;

  const stop = useCallback(() => {
    stopped.current = true;
    setCaption(null);
    setDone(false);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    stopped.current = false;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = reduce ? "auto" : "smooth";
    class Stop extends Error {}
    const wait = (ms: number) =>
      new Promise<void>((resolve, reject) =>
        setTimeout(() => (stopped.current ? reject(new Stop()) : resolve()), ms),
      );
    const until = async (ok: () => boolean, timeout = 90_000) => {
      const t0 = Date.now();
      while (!ok()) {
        if (Date.now() - t0 > timeout) throw new Error("timeout");
        await wait(200);
      }
    };
    const el = (sel: string) => document.querySelector<HTMLElement>(sel);
    const enabledBtn = (sel: string) => {
      const b = el(sel) as HTMLButtonElement | null;
      return !!b && !b.disabled;
    };
    const show = (sel: string, block: ScrollLogicalPosition = "start") => {
      const e = el(sel);
      if (!e) return;
      const top = e.getBoundingClientRect().top + window.scrollY - (block === "start" ? 72 : window.innerHeight / 3);
      window.scrollTo({ top, behavior });
    };
    const type = async (s: string) => {
      if (reduce) return setText(s);
      for (let i = 0; i <= s.length; i += 3) {
        setText(s.slice(0, i));
        await wait(16);
      }
      setText(s);
    };
    const say = (i: number, text: string) => {
      setStep(i);
      setCaption(text);
    };
    const runOne = async (text: string) => {
      window.scrollTo({ top: 0, behavior });
      await wait(1200);
      await type(text);
      await wait(1500);
      el('[data-tour="compile"]')?.click();
      await until(() => !el("#report-title"));
      await until(() => enabledBtn('[data-tour="verify"]'));
      await wait(1400);
      el('[data-tour="verify"]')?.click();
      await until(() => !!el("#report-title"));
      await wait(300);
    };

    (async () => {
      try {
        say(1, "Chuyên viên viết luật bằng tiếng Việt, để đỡ phiền cho khách thân thiết.");
        await wait(1000);
        await runOne(texts[0]);
        say(2, "Z3 xét mọi giao dịch có thể có và trả về kết luận cùng câu tóm tắt.");
        show("#report-title");
        await wait(4500);
        say(3, "Lỗ hổng cụ thể: một giao dịch lọt qua mà không cần sinh trắc học, trái quy định.");
        show('[data-tour="cex"]');
        await wait(5000);

        say(4, "Phần 2: một luật nghe rất an toàn, miễn xác thực khi thanh toán QR cho merchant đã xác minh.");
        await runOne(texts[1]);
        const unseen = (reportRef.current?.checks ?? []).some((c) => c.code === "VC-04" && c.grounding?.tx_count === 0);
        say(
          5,
          unseen
            ? "Lỗ hổng này chưa từng xảy ra trong dữ liệu cũ: chạy thử trên dữ liệu bỏ sót, Z3 vẫn bắt được."
            : "So với chạy thử trên dữ liệu cũ: Z3 thấy mọi lỗ hổng, kèm giao dịch cụ thể.",
        );
        show('[data-tour="datavsz3"]');
        await wait(8000);

        say(6, "Sửa bằng AI: mỗi bản sửa được kiểm chứng lại và tính tổn thất trước khi hiện ra.");
        show('[data-tour="repair"]', "center");
        await wait(1200);
        el('[data-tour="repair"]')?.click();
        await until(() => !!el("#repair-title"));
        show("#repair-title");
        await wait(5000);

        say(7, "Xong Demo 1. Tiếp theo: gửi đề xuất để người duyệt ký, hoặc xem Demo 2 và Demo 3.");
        setDone(true);
      } catch (e) {
        if (e instanceof Stop) return;
        setFailed(true);
        setCaption("Không chạy tiếp được (máy chủ chậm hoặc AI không phản hồi). Bạn có thể tự bấm các nút trên trang.");
      }
    })();
    return () => {
      stopped.current = true;
    };
  }, [enabled, setText, texts]);

  useEffect(() => {
    if (!caption) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && stop();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [caption, stop]);

  if (!enabled || !caption) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-4 bottom-20 z-40 mx-auto max-w-xl rounded-lg border border-line bg-surface p-4 shadow-pop md:bottom-6"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="num text-xs text-muted">
          Demo tự chạy · {Math.min(step, TOTAL)}/{TOTAL}
        </p>
        <span aria-hidden className="flex gap-1">
          {Array.from({ length: TOTAL }, (_, i) => (
            <span key={i} className={`h-1 w-5 rounded-full ${i < step ? "bg-foreground" : "bg-line"}`} />
          ))}
        </span>
      </div>
      <p className="mt-2 text-[0.9375rem] leading-6 font-medium">{caption}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {done || failed ? (
          <>
            <Link href={`/s/${sid}/pack?demo=2`} className="btn btn-primary btn-sm">
              Xem Demo 2
            </Link>
            <Link href={`/s/${sid}/compare?demo=3`} className="btn btn-secondary btn-sm">
              Xem Demo 3
            </Link>
            <button type="button" onClick={stop} className="btn btn-ghost btn-sm ml-auto">
              Đóng
            </button>
          </>
        ) : (
          <button type="button" onClick={stop} className="btn btn-secondary btn-sm">
            Dừng, tôi tự thử
          </button>
        )}
      </div>
    </div>
  );
}
