"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { RepairPanel } from "@/components/RepairPanel";
import { RuleSentence } from "@/components/RuleSentence";
import { VerifyReportView } from "@/components/VerifyReportView";
import { ApiError, api } from "@/lib/api";
import { KIND_VI } from "@/lib/format";
import type { Catalog, CompileResult, PolicyPack, RepairCandidate, RepairResponse, Rule, VerifyReport } from "@/lib/types";

const DEMO1 =
  "Để giảm phiền hà cho khách thân thiết: tài khoản trên 1 năm, chuyển cho người nhận quen thì không cần xác thực thêm.";

const SUGGESTIONS = [
  "Tài khoản mới dưới 7 ngày nhận tiền từ 5 người trong 1 giờ rồi chuyển đi gần hết thì giữ lại 2 phút.",
  "Chuyển tiền từ 5 triệu trở lên lúc nửa đêm cho tài khoản nhận mới mở dưới 3 ngày thì gắn cờ giám sát.",
  "Thanh toán QR cho merchant đã xác minh dưới 500 nghìn thì miễn xác thực thêm.",
];

// Mẫu để viết luật bằng JSON khi AI không khả dụng (do người viết, không phải kết quả AI).
const JSON_TEMPLATE = {
  id: "DRAFT-0001",
  name: "Luật viết tay",
  kind: "FRICTION",
  status: "CANDIDATE",
  when: {
    all: [
      { field: "sender_account_age_days", op: ">", value: 365 },
      { field: "receiver_is_familiar", op: "==", value: true },
    ],
  },
  then: { exempt_auth: true },
};

type Phase = "idle" | "compiling" | "compiled" | "verifying" | "done" | "repairing";

function withoutRender(rule: Rule): Omit<Rule, "render"> {
  const { render: _render, ...rest } = rule;
  void _render;
  return rest;
}

export function StudioView() {
  const { sid } = useParams<{ sid: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const [text, setText] = useState(() => (search.get("demo") === "1" ? DEMO1 : ""));
  const [phase, setPhase] = useState<Phase>("idle");
  const [compiled, setCompiled] = useState<CompileResult | null>(null);
  const [rule, setRule] = useState<Rule | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [jsonDirty, setJsonDirty] = useState(false);
  const [manual, setManual] = useState(false);
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pack, setPack] = useState<PolicyPack | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [verified, setVerified] = useState<Record<string, unknown>[]>([]);
  const [repair, setRepair] = useState<RepairResponse | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const repairRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.pack(sid).then(setPack).catch(() => undefined);
    api.catalog().then(setCatalog).catch(() => undefined);
  }, [sid]);

  function startManualJson(message: string | null) {
    setBanner(message);
    setManual(true);
    setRule(null);
    setCompiled(null);
    setJsonText(JSON.stringify(JSON_TEMPLATE, null, 2));
    setJsonDirty(true);
    setPhase("compiled");
  }

  async function onCompile(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setPhase("compiling");
    setError(null);
    setBanner(null);
    setReport(null);
    setRepair(null);
    setSavedNote(null);
    setManual(false);
    try {
      const res = await api.compile(sid, text);
      setCompiled(res);
      setRule(res.rule);
      setJsonText(res.rule ? JSON.stringify(withoutRender(res.rule), null, 2) : "");
      setJsonDirty(false);
      setPhase("compiled");
    } catch (err) {
      if (err instanceof ApiError && (err.code === "LLM_UNAVAILABLE" || err.code === "LLM_QUOTA")) {
        startManualJson(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Biên dịch thất bại.");
        setPhase("idle");
      }
    }
  }

  async function verifyRules(bodies: Record<string, unknown>[]) {
    setError(null);
    setSavedNote(null);
    setPhase("verifying");
    try {
      const rep = await api.verify(sid, bodies);
      setReport(rep);
      setVerified(bodies);
      setPhase("done");
      requestAnimationFrame(() => reportRef.current?.focus());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kiểm chứng thất bại.");
      setPhase("compiled");
    }
  }

  async function onVerify() {
    let body: Record<string, unknown>;
    try {
      body = jsonDirty || !rule ? JSON.parse(jsonText) : withoutRender(rule);
    } catch {
      setError("JSON không hợp lệ — kiểm tra lại dấu ngoặc, dấu phẩy.");
      return;
    }
    setRepair(null);
    await verifyRules([body]);
  }

  async function onRepair() {
    if (verified.length === 0) return;
    setError(null);
    setPhase("repairing");
    try {
      setRepair(await api.repair(sid, verified[0]));
      requestAnimationFrame(() => repairRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được bản sửa.");
    } finally {
      setPhase("done");
    }
  }

  async function onUse(c: RepairCandidate) {
    const [first] = c.rules;
    setRule(first);
    setManual(false);
    setJsonText(JSON.stringify(withoutRender(first), null, 2));
    setJsonDirty(false);
    await verifyRules(c.rules.map((r) => withoutRender(r) as unknown as Record<string, unknown>));
    requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  async function onSave() {
    try {
      const results = await Promise.all(verified.map((r) => api.saveRule(sid, r)));
      const ids = results.filter((r) => r.saved && r.rule).map((r) => `${r.rule!.id} v${r.rule!.version}`);
      setSavedNote(ids.length ? `Đã lưu ${ids.join(", ")} vào bộ luật của sandbox (trạng thái ứng viên).` : "Không lưu được luật.");
    } catch (err) {
      setSavedNote(err instanceof ApiError ? err.message : "Không lưu được luật.");
    }
  }

  async function onChangeSet() {
    try {
      const cs = await api.createChangeSet(
        sid,
        verified.map((r) => ({ rule: r })),
        `Tạo từ Rule Studio${text ? `: “${text.slice(0, 200)}”` : ""}`,
      );
      router.push(`/s/${sid}/review?cs=${cs.id}`);
    } catch (err) {
      setSavedNote(err instanceof ApiError ? err.message : "Không tạo được change set.");
    }
  }

  const nInv = pack?.invariants.length ?? 3;
  const progress =
    phase === "compiling"
      ? "AI đang biên dịch…"
      : phase === "verifying"
        ? `Đang kiểm chứng ${nInv} invariant bằng Z3…`
        : phase === "repairing"
          ? "Đang đề xuất bản sửa, kiểm chứng lại và backtest từng bản…"
          : "";
  const busy = phase === "verifying" || phase === "compiling" || phase === "repairing";
  const canVerify = (rule !== null || manual) && !busy;
  const draftId = verified[0]?.id;
  const blamed = report?.checks.some((c) => c.code === "VC-04" && c.blamed_rules?.includes(String(draftId))) ?? false;
  const passed = report !== null && (report.verdict === "PASS" || report.verdict === "PASS_WITH_WARNINGS");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Rule Studio</h1>
        <p className="text-sm text-muted">Viết luật bằng tiếng Việt → AI biên dịch → Z3 kiểm chứng với Policy Pack.</p>
      </header>

      {banner && (
        <div role="alert" className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {banner}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Cột trái: yêu cầu tiếng Việt */}
        <section aria-labelledby="req-title" className="space-y-4">
          <form onSubmit={onCompile} className="space-y-3 rounded-2xl border border-line bg-surface p-4">
            <label id="req-title" htmlFor="requirement" className="block font-semibold">
              Yêu cầu luật (tiếng Việt)
            </label>
            <textarea
              id="requirement"
              name="requirement"
              rows={5}
              maxLength={1000}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={DEMO1}
              aria-describedby="req-help"
              className="w-full rounded-xl border border-zinc-400 bg-background p-3 leading-6 dark:border-zinc-600"
            />
            <p id="req-help" className="text-xs text-muted">
              Tối đa 1.000 ký tự. AI chỉ đề xuất luật; kết luận đạt/không đạt do bộ kiểm chứng tính.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={phase === "compiling" || phase === "verifying"}
                className="min-h-11 rounded-xl bg-accent px-5 font-semibold text-white hover:opacity-90 disabled:opacity-60 dark:text-zinc-950"
              >
                Biên dịch
              </button>
              <button
                type="button"
                onClick={() => startManualJson(null)}
                className="min-h-11 rounded-xl border border-line px-4 text-sm hover:bg-background"
              >
                Viết luật bằng JSON
              </button>
            </div>
          </form>

          <div className="space-y-2">
            <p className="text-sm font-medium text-muted">Thử câu khác:</p>
            <ul className="flex flex-col gap-2">
              {[DEMO1, ...SUGGESTIONS].map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => setText(s)}
                    className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-left text-sm hover:border-accent"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Cột phải: thẻ luật */}
        <section aria-labelledby="rule-title" className="space-y-3">
          <h2 id="rule-title" className="sr-only">
            Luật sau biên dịch
          </h2>
          <p role="status" aria-live="polite" className="min-h-6 text-sm font-medium text-accent">
            {progress}
          </p>
          {error && (
            <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-danger dark:bg-red-950">
              {error}
            </p>
          )}
          {phase === "idle" && !error && (
            <div className="rounded-2xl border border-dashed border-line p-6 text-sm text-muted">
              Luật sau khi biên dịch sẽ hiện ở đây, kèm các giả định để bạn xác nhận trước khi kiểm chứng.
            </div>
          )}
          {compiled && compiled.status !== "OK" && <CompileNotice result={compiled} />}
          {(rule || manual) && (
            <RuleCard
              rule={rule}
              compiled={compiled}
              manual={manual}
              jsonText={jsonText}
              jsonDirty={jsonDirty}
              onJsonChange={(v) => {
                setJsonText(v);
                setJsonDirty(true);
              }}
            />
          )}
          {canVerify && (
            <button
              type="button"
              onClick={onVerify}
              className="min-h-14 w-full rounded-2xl bg-zinc-900 text-lg font-bold text-white shadow hover:opacity-90 dark:bg-white dark:text-zinc-900"
            >
              Kiểm chứng
            </button>
          )}
        </section>
      </div>

      {report && (
        <div ref={reportRef} tabIndex={-1} className="outline-none">
          <VerifyReportView
            report={report}
            pack={pack}
            catalog={catalog}
            actions={
              <div className="flex flex-wrap items-center gap-3">
                {blamed && (
                  <button
                    type="button"
                    onClick={onRepair}
                    disabled={busy}
                    className="min-h-12 rounded-xl bg-accent px-6 font-semibold text-white hover:opacity-90 disabled:opacity-60 dark:text-zinc-950"
                  >
                    Sửa bằng AI
                  </button>
                )}
                {passed && verified.length > 0 && (
                  <button
                    type="button"
                    onClick={onSave}
                    className="min-h-12 rounded-xl border border-line px-5 font-semibold hover:bg-background"
                  >
                    Lưu vào bộ luật (ứng viên)
                  </button>
                )}
                {verified.length > 0 && (
                  <button
                    type="button"
                    onClick={onChangeSet}
                    disabled={busy}
                    className="min-h-12 rounded-xl border border-line px-5 font-semibold hover:bg-background disabled:opacity-60"
                  >
                    Tạo change set để duyệt
                  </button>
                )}
                <p role="status" className="text-sm text-ok">
                  {savedNote}
                </p>
              </div>
            }
          />
        </div>
      )}

      {repair && (
        <div ref={repairRef}>
          <RepairPanel data={repair} onUse={onUse} busy={busy} />
        </div>
      )}
    </div>
  );
}

function CompileNotice({ result }: { result: CompileResult }) {
  if (result.status === "OUT_OF_SCOPE") {
    return (
      <div className="rounded-2xl border border-line bg-surface p-4 text-sm">
        Mình chưa hiểu đây là luật rủi ro giao dịch. Thử mô tả điều kiện (số tiền, kênh, thời gian, tài khoản…) và hành
        động (giữ lại, chặn, yêu cầu xác thực…), ví dụ: “{SUGGESTIONS[0]}”
      </div>
    );
  }
  if (result.status === "NEEDS_CLARIFICATION") {
    return (
      <div className="space-y-2 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        <p className="font-semibold">Cần làm rõ:</p>
        <ul className="list-disc pl-5">
          {result.clarifying_questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-danger dark:border-red-900 dark:bg-red-950">
      <p className="font-semibold">AI chưa tạo được luật hợp lệ sau 2 lần thử:</p>
      <ul className="list-disc pl-5">
        {result.errors.map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ul>
      <p>Bạn có thể viết lại câu cho rõ hơn, hoặc viết luật bằng JSON.</p>
    </div>
  );
}

function RuleCard({
  rule,
  compiled,
  manual,
  jsonText,
  jsonDirty,
  onJsonChange,
}: {
  rule: Rule | null;
  compiled: CompileResult | null;
  manual: boolean;
  jsonText: string;
  jsonDirty: boolean;
  onJsonChange: (v: string) => void;
}) {
  const [tab, setTab] = useState<"sentence" | "json">(manual ? "json" : "sentence");
  const id = useId();
  const tabs = [
    { key: "sentence" as const, label: "Câu tiếng Việt" },
    { key: "json" as const, label: "JSON" },
  ];

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const next = tab === "sentence" ? "json" : "sentence";
    const target = e.key === "Home" ? "sentence" : e.key === "End" ? "json" : next;
    setTab(target);
    document.getElementById(`${id}-${target}-tab`)?.focus();
  }

  const by = rule?.provenance?.created_by;
  const source = manual
    ? "Người viết (JSON)"
    : by === "det_repair"
      ? "Sửa tất định"
      : by === "ai_repair"
        ? "AI sửa"
        : by === "human"
          ? "Người viết"
          : compiled?.source === "cache"
            ? "AI · kết quả đã lưu"
            : "AI đề xuất";

  return (
    <article className="space-y-4 rounded-2xl border border-line bg-surface p-4">
      <header className="flex flex-wrap items-center gap-2">
        {rule && <span className="font-mono text-sm font-semibold">{rule.id}</span>}
        {rule && <span className="font-semibold">{rule.name}</span>}
        {rule && <span className="rounded-full bg-background px-2 py-0.5 text-xs">{KIND_VI[rule.kind]}</span>}
        <span className="ml-auto rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-900 dark:bg-violet-950 dark:text-violet-200">
          {source}
        </span>
      </header>

      <div role="tablist" aria-label="Cách xem luật" className="flex gap-4 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`${id}-${t.key}-tab`}
            aria-selected={tab === t.key}
            tabIndex={tab === t.key ? 0 : -1}
            onClick={() => setTab(t.key)}
            onKeyDown={onTabKey}
            className="pb-2 text-sm font-medium"
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-labelledby={`${id}-sentence-tab`} hidden={tab !== "sentence"}>
        <div className="space-y-4">
          {rule?.render ? (
            <RuleSentence render={rule.render} />
          ) : (
            <p className="text-sm text-muted">Luật viết bằng JSON — câu tiếng Việt sẽ hiện trong kết quả kiểm chứng.</p>
          )}
          {jsonDirty && rule && <p className="text-xs text-warn">JSON đã được sửa; bản sửa sẽ được dùng khi kiểm chứng.</p>}
          {compiled && compiled.assumptions.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium">Giả định (hãy xác nhận):</p>
              <ul className="flex flex-wrap gap-2">
                {compiled.assumptions.map((a) => (
                  <li key={a.phrase} className="rounded-full border border-line bg-background px-3 py-1 text-xs">
                    <span className="font-semibold">“{a.phrase}”</span> = {a.interpretation}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {compiled && compiled.unsupported_parts.length > 0 && (
            <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
              <p className="font-semibold">Phần chưa biểu diễn được:</p>
              <ul className="list-disc pl-5">
                {compiled.unsupported_parts.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <div role="tabpanel" aria-labelledby={`${id}-json-tab`} hidden={tab !== "json"}>
        <label htmlFor={`${id}-json`} className="sr-only">
          Luật dạng JSON
        </label>
        <textarea
          id={`${id}-json`}
          value={jsonText}
          onChange={(e) => onJsonChange(e.target.value)}
          rows={14}
          spellCheck={false}
          className="w-full rounded-xl border border-zinc-400 bg-background p-3 font-mono text-sm dark:border-zinc-600"
        />
      </div>
    </article>
  );
}
