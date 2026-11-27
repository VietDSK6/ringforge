"use client";

import { type FormEvent, useId, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { formatInt, formatVnd } from "@/lib/format";
import type { InterpretResult, PatchOp } from "@/lib/types";

const SAMPLE = "Từ 01/01/2027, giao dịch chuyển tiền trên 5 triệu đồng/lần phải xác thực sinh trắc học (kịch bản giả lập).";

const fmt = (v: number, unit: string) => (unit === "VND" ? formatVnd(v) : `${formatInt(v)} ${unit === "s" ? "giây" : unit}`);

/** FR-P4: dán mô tả quy định mới → AI đề xuất bản vá Policy Pack. Chỉ là đề xuất: người dùng phân tích tác động rồi tự áp dụng. */
export function RegulationInterpreter({ sid, onUse }: { sid: string; onUse: (patch: PatchOp[]) => void }) {
  const uid = useId();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<InterpretResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.packInterpret(sid, text));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không diễn giải được văn bản.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby={`${uid}-title`} className="space-y-3 rounded-2xl border border-line bg-surface p-4">
      <div>
        <h2 id={`${uid}-title`} className="text-lg font-semibold">
          Dán mô tả quy định mới
        </h2>
        <p className="text-sm text-muted">AI đọc văn bản và đề xuất bản vá Policy Pack. Không có gì thay đổi cho đến khi bạn phân tích tác động và áp dụng.</p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <label htmlFor={`${uid}-text`} className="sr-only">
          Mô tả quy định
        </label>
        <textarea
          id={`${uid}-text`}
          rows={3}
          maxLength={1000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={SAMPLE}
          className="w-full rounded-xl border border-zinc-400 bg-background p-3 leading-6 dark:border-zinc-600"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="min-h-11 rounded-xl bg-accent px-5 font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-zinc-950"
          >
            {busy ? "AI đang đọc văn bản…" : "Đề xuất bản vá"}
          </button>
          <button type="button" onClick={() => setText(SAMPLE)} className="min-h-11 text-sm text-accent underline">
            Điền ví dụ
          </button>
        </div>
      </form>
      {error && (
        <p role="alert" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {error}
        </p>
      )}
      {result && (
        <div role="status" className="space-y-2 rounded-xl bg-background p-3 text-sm">
          <p className="text-xs text-accent">AI đề xuất · đã kiểm cấu trúc và hợp lệ với Policy Pack (VC-01)</p>
          {result.status === "OUT_OF_SCOPE" && <p>Văn bản này không nói về quy định xác thực/giao dịch thanh toán — không có bản vá.</p>}
          {result.status === "INVALID" && (
            <>
              <p className="font-semibold text-danger">Bản vá AI đề xuất không hợp lệ nên không dùng được:</p>
              <ul className="list-disc pl-5 text-danger">
                {(result.errors ?? []).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </>
          )}
          {result.status === "OK" && (
            <>
              <ul className="list-disc space-y-1 pl-5">
                {result.changes.map((c, i) => (
                  <li key={i}>
                    {c.op === "set_param" ? (
                      <>
                        {c.label_vi}: {fmt(c.old, c.unit)} → <strong>{fmt(c.new, c.unit)}</strong>
                      </>
                    ) : c.op === "add_invariant" ? (
                      <>
                        Thêm <span className="font-mono">{c.invariant_id}</span>: {c.description_vi}
                      </>
                    ) : (
                      <>Bỏ {c.invariant_id}</>
                    )}
                  </li>
                ))}
              </ul>
              {result.effective_date && <p>Hiệu lực: {new Date(result.effective_date).toLocaleDateString("vi-VN")}</p>}
              <button
                type="button"
                onClick={() => onUse(result.patch)}
                className="min-h-11 rounded-xl border-2 border-accent px-4 font-semibold text-accent hover:bg-violet-50 dark:hover:bg-violet-950"
              >
                Dùng bản vá này để phân tích tác động
              </button>
            </>
          )}
          {result.uncertainties.length > 0 && (
            <div>
              <p className="font-medium">Điểm cần pháp chế xác nhận:</p>
              <ul className="list-disc pl-5 text-muted">
                {result.uncertainties.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
