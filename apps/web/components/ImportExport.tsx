"use client";

import { type FormEvent, useId, useRef, useState } from "react";

import { Callout } from "@/components/Callout";
import { ApiError, api } from "@/lib/api";
import type { VerifyReport } from "@/lib/types";

const SAMPLE = {
  mode: "merge",
  rules: [
    {
      id: "MY-01",
      name: "Giữ chuyển lớn ban đêm cho tài khoản nhận mới",
      kind: "FRAUD",
      status: "ACTIVE",
      when: {
        all: [
          { field: "amount", op: ">=", value: 3000000 },
          { field: "receiver_account_age_days", op: "<", value: 3 },
          { field: "hour", op: "between", value: [0, 5] },
        ],
      },
      then: { decision: "HOLD", hold_seconds: 120 },
    },
  ],
};

/** Nhập/xuất bộ luật + Policy Pack dạng JSON (FR-S8). Nhập xong kiểm chứng ngay. */
export function ImportExport({ sid, onImported }: { sid: string; onImported: (report: VerifyReport) => void }) {
  const uid = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"replace" | "merge">("merge");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);

  async function download() {
    setNote(null);
    try {
      const data = await api.exportRuleset(sid);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ringforge-bo-luat-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Không xuất được bộ luật.");
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setText(await file.text());
    setErrors([]);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    let body: Record<string, unknown>;
    try {
      const parsed = JSON.parse(text);
      body = Array.isArray(parsed) ? { rules: parsed } : parsed;
    } catch {
      setErrors(["JSON không hợp lệ — kiểm tra lại dấu ngoặc, dấu phẩy, dấu nháy."]);
      return;
    }
    setBusy(true);
    setErrors([]);
    try {
      const res = await api.importRuleset(sid, { ...body, mode });
      dialogRef.current?.close();
      setNote(`Đã nhập ${res.imported.rules} luật${res.imported.policy_pack ? ` và Policy Pack ${res.imported.policy_pack}` : ""}; đã kiểm chứng lại toàn bộ ${res.rules_total} luật.`);
      onImported(res.verify);
    } catch (err) {
      if (err instanceof ApiError) {
        const details = Array.isArray(err.details)
          ? (err.details as { message_vi?: string; path?: string }[]).map((d) => `${d.path ? `${d.path}: ` : ""}${d.message_vi ?? ""}`)
          : [];
        setErrors([err.message, ...details]);
      } else {
        setErrors(["Không nhập được bộ luật."]);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={download} className="btn btn-secondary">
        Xuất JSON
      </button>
      <button type="button" onClick={() => dialogRef.current?.showModal()} className="btn btn-secondary">
        Nhập JSON
      </button>
      {note && (
        <p role="status" className="w-full text-sm text-pass">
          {note}
        </p>
      )}

      <dialog
        ref={dialogRef}
        aria-labelledby={`${uid}-title`}
        className="m-auto max-h-[calc(100dvh-2rem)] w-[min(44rem,calc(100%-2rem))] overflow-y-auto rounded-xl border border-line bg-surface p-6 text-foreground shadow-pop"
      >
        <form onSubmit={submit} className="space-y-4">
          <h1 id={`${uid}-title`} className="text-lg font-bold">
            Nhập bộ luật / Policy Pack
          </h1>
          <p className="text-sm leading-6 text-muted">
            Dán JSON theo rf-dsl/0.1: một mảng luật, hoặc object có <code className="font-mono">rules</code> và/hoặc{" "}
            <code className="font-mono">policy_pack</code> (đúng định dạng file Xuất JSON). Bộ luật được kiểm chứng ngay sau khi nhập.
          </p>
          <div>
            <label htmlFor={`${uid}-file`} className="label">
              Chọn file .json
            </label>
            <input
              id={`${uid}-file`}
              type="file"
              accept="application/json,.json"
              onChange={(e) => onFile(e.target.files?.[0])}
              className="mt-1 block w-full text-sm file:mr-3 file:min-h-10 file:cursor-pointer file:rounded-md file:border file:border-line-strong file:bg-surface file:px-3 file:font-medium file:text-foreground hover:file:bg-sunken"
            />
          </div>
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <label htmlFor={`${uid}-json`} className="label">
                Hoặc dán JSON
              </label>
              <button type="button" onClick={() => setText(JSON.stringify(SAMPLE, null, 2))} className="btn btn-ghost btn-sm">
                Điền ví dụ
              </button>
            </div>
            <textarea
              id={`${uid}-json`}
              rows={8}
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              aria-describedby={errors.length ? `${uid}-err` : undefined}
              aria-invalid={errors.length > 0 || undefined}
              className="field field-mono mt-1 bg-sunken"
            />
          </div>
          <fieldset className="space-y-1">
            <legend className="label">Cách nhập luật</legend>
            <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm">
              <input type="radio" name={`${uid}-mode`} checked={mode === "merge"} onChange={() => setMode("merge")} />
              Thêm vào bộ luật hiện tại (luật trùng mã sẽ được thay; luật pháp lý khóa được giữ nguyên)
            </label>
            <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm">
              <input type="radio" name={`${uid}-mode`} checked={mode === "replace"} onChange={() => setMode("replace")} />
              Thay toàn bộ bộ luật của sandbox bằng bộ luật nhập vào
            </label>
          </fieldset>
          {errors.length > 0 && (
            <Callout tone="fail" role="alert" id={`${uid}-err`}>
              <ul className="list-disc space-y-1 pl-4">
                {errors.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </Callout>
          )}
          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="btn btn-secondary"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="btn btn-primary"
            >
              {busy ? "Đang nhập và kiểm chứng…" : "Nhập và kiểm chứng"}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
