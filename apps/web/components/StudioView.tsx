"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { Callout } from "@/components/Callout";
import { GuidedTour, type TourStep } from "@/components/GuidedTour";
import { RepairPanel } from "@/components/RepairPanel";
import { RuleSentence } from "@/components/RuleSentence";
import { type Source, SourceTag } from "@/components/SourceTag";
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

const TOUR: TourStep[] = [
  { target: "req", text: "Câu Demo 1 đã điền sẵn; bạn có thể sửa câu chữ." },
  { target: "compile", text: "Bấm Biên dịch: AI chuyển câu thành luật có cấu trúc.", advanceOn: "click" },
  {
    target: "verify",
    text: "Bấm Kiểm chứng: Z3 xét mọi giao dịch có thể có.",
    advanceOn: "click",
    waiting: "Chờ luật biên dịch xong (AI tắt thì dùng mẫu JSON).",
  },
  { target: "cex", text: "Phản ví dụ: một giao dịch cụ thể lọt qua sinh trắc học.", waiting: "Chờ kết quả kiểm chứng…" },
  { target: "repair", text: "Bấm Sửa bằng AI: mọi bản sửa đều được kiểm chứng lại.", advanceOn: "click" },
];

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

  const done = [text.trim() !== "", rule !== null || manual, report !== null, repair !== null];
  const running = phase === "compiling" ? 1 : phase === "verifying" ? 2 : phase === "repairing" ? 3 : -1;
  const current = running >= 0 ? running : done.indexOf(false);

  return (
    <div className="space-y-6">
      <GuidedTour id="demo1" steps={TOUR} enabled={search.get("demo") === "1"} />
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <h1 className="page-title">Rule Studio</h1>
          <p className="page-lede">Viết luật bằng tiếng Việt → AI biên dịch → Z3 kiểm chứng với Policy Pack.</p>
        </div>
        <Stepper steps={["Viết yêu cầu", "Biên dịch", "Kiểm chứng", "Sửa / duyệt"]} done={done} current={current} running={running >= 0} />
      </header>

      {banner && (
        <Callout tone="warn" role="alert">
          {banner}
        </Callout>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-2">
        {/* Cột trái: yêu cầu tiếng Việt */}
        <section aria-labelledby="req-title" className="panel">
          <form onSubmit={onCompile} className="space-y-3 p-4 sm:p-5">
            <label id="req-title" htmlFor="requirement" className="section-title block">
              Yêu cầu luật (tiếng Việt)
            </label>
            <textarea
              id="requirement"
              data-tour="req"
              name="requirement"
              rows={5}
              maxLength={1000}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={DEMO1}
              aria-describedby="req-help"
              className="field resize-y leading-7"
            />
            <p id="req-help" className="text-[0.8125rem] text-muted">
              Tối đa 1.000 ký tự. AI chỉ đề xuất luật; kết luận đạt/không đạt do bộ kiểm chứng tính.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="submit"
                data-tour="compile"
                disabled={phase === "compiling" || phase === "verifying"}
                className="btn btn-primary"
              >
                Biên dịch
              </button>
              <button type="button" onClick={() => startManualJson(null)} className="btn btn-secondary">
                Viết luật bằng JSON
              </button>
            </div>
          </form>

          <div className="border-t border-line p-4 sm:p-5">
            <p className="label mb-2">Thử câu khác</p>
            <ul className="-mx-2 space-y-0.5">
              {[DEMO1, ...SUGGESTIONS].map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => setText(s)}
                    aria-pressed={text === s}
                    className={`block w-full rounded-md px-2 py-2 text-left text-sm leading-6 ${
                      text === s ? "bg-sunken font-medium text-foreground" : "text-muted hover:bg-sunken hover:text-foreground"
                    }`}
                  >
                    <span>{s}</span>
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
          <p role="status" aria-live="polite" className={`flex min-h-6 items-center gap-2 text-sm font-medium text-accent ${progress ? "" : "sr-only"}`}>
            {progress && <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent" />}
            {progress}
          </p>
          {error && (
            <Callout tone="fail" role="alert">
              {error}
            </Callout>
          )}
          {phase === "idle" && !error && (
            <div className="empty p-5">
              <p className="max-w-md">Luật sau khi biên dịch sẽ hiện ở đây, kèm các giả định để bạn xác nhận trước khi kiểm chứng.</p>
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
            <button type="button" onClick={onVerify} data-tour="verify" className="btn btn-primary min-h-14 w-full text-lg font-semibold">
              Kiểm chứng
            </button>
          )}
        </section>
      </div>

      {report && (
        <div ref={reportRef} tabIndex={-1} className="scroll-mt-16 outline-none">
          <VerifyReportView
            report={report}
            pack={pack}
            catalog={catalog}
            actions={
              <div className="flex flex-wrap items-center gap-3">
                {blamed && (
                  <button type="button" onClick={onRepair} data-tour="repair" disabled={busy} className="btn btn-primary btn-lg">
                    Sửa bằng AI
                  </button>
                )}
                {passed && verified.length > 0 && (
                  <button type="button" onClick={onSave} className="btn btn-secondary btn-lg">
                    Lưu vào bộ luật (ứng viên)
                  </button>
                )}
                {verified.length > 0 && (
                  <button type="button" onClick={onChangeSet} disabled={busy} className="btn btn-secondary btn-lg">
                    Tạo change set để duyệt
                  </button>
                )}
                <p role="status" className="text-sm text-pass">
                  {savedNote}
                </p>
              </div>
            }
          />
        </div>
      )}

      {repair && (
        <div ref={repairRef} className="scroll-mt-16">
          <RepairPanel data={repair} onUse={onUse} busy={busy} />
        </div>
      )}
    </div>
  );
}

/** Tiến trình pipeline của Studio: viết → biên dịch → kiểm chứng → sửa. */
function Stepper({ steps, done, current, running }: { steps: string[]; done: boolean[]; current: number; running: boolean }) {
  return (
    <ol aria-label="Tiến trình" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem]">
      {steps.map((s, i) => {
        const isCurrent = i === current;
        const isDone = done[i] && !isCurrent;
        return (
          <li
            key={s}
            aria-current={isCurrent ? "step" : undefined}
            className={`flex items-baseline gap-1.5 border-b-2 pb-1 ${
              isCurrent ? "border-foreground font-semibold text-foreground" : isDone ? "border-transparent text-foreground" : "border-transparent text-faint"
            } ${isCurrent && running ? "animate-pulse" : ""}`}
          >
            <span className={`num ${isDone ? "text-pass" : ""}`}>{isDone ? "✓" : `${i + 1}.`}</span>
            {s}
            <span className="sr-only">{isDone ? " (xong)" : isCurrent ? " (bước hiện tại)" : ""}</span>
          </li>
        );
      })}
    </ol>
  );
}

function CompileNotice({ result }: { result: CompileResult }) {
  if (result.status === "OUT_OF_SCOPE") {
    return (
      <Callout tone="info">
        Mình chưa hiểu đây là luật rủi ro giao dịch. Thử mô tả điều kiện (số tiền, kênh, thời gian, tài khoản…) và hành động (giữ lại,
        chặn, yêu cầu xác thực…), ví dụ: “{SUGGESTIONS[0]}”
      </Callout>
    );
  }
  if (result.status === "NEEDS_CLARIFICATION") {
    return (
      <Callout tone="warn" title="Cần làm rõ:">
        <ul className="list-disc pl-5">
          {result.clarifying_questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      </Callout>
    );
  }
  return (
    <Callout tone="fail" title="AI chưa tạo được luật hợp lệ sau 2 lần thử:">
      <ul className="list-disc pl-5">
        {result.errors.map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ul>
      <p>Bạn có thể viết lại câu cho rõ hơn, hoặc viết luật bằng JSON.</p>
    </Callout>
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
  const source: { kind: Source; label: string } = manual
    ? { kind: "human", label: "Người viết (JSON)" }
    : by === "det_repair"
      ? { kind: "det", label: "Sửa tất định" }
      : by === "ai_repair"
        ? { kind: "ai", label: "AI sửa" }
        : by === "human"
          ? { kind: "human", label: "Người viết" }
          : compiled?.source === "cache"
            ? { kind: "cache", label: "AI · kết quả đã lưu" }
            : { kind: "ai", label: "AI đề xuất" };

  return (
    <article className="panel">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 pt-4 sm:px-5">
        {rule && <span className="font-mono text-sm font-semibold">{rule.id}</span>}
        {rule && <span className="font-semibold">{rule.name}</span>}
        {rule && <span className="chip text-muted">{KIND_VI[rule.kind]}</span>}
        <SourceTag source={source.kind} label={source.label} className="ml-auto" />
      </header>

      <div role="tablist" aria-label="Cách xem luật" className="mt-3 flex gap-5 border-b border-line px-4 sm:px-5">
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
            className={`min-h-11 text-sm font-medium ${tab === t.key ? "" : "text-muted hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-labelledby={`${id}-sentence-tab`} hidden={tab !== "sentence"} className="p-4 sm:p-5">
        <div className="space-y-4">
          {rule?.render ? (
            <RuleSentence render={rule.render} />
          ) : (
            <p className="text-sm text-muted">
              Luật viết bằng JSON (mẫu điền sẵn do người viết cho câu Demo 1, không phải kết quả AI) — câu tiếng Việt sẽ hiện trong kết quả
              kiểm chứng.
            </p>
          )}
          {jsonDirty && rule && (
            <p className="flex items-center gap-2 text-[0.8125rem] text-warn">
              JSON đã được sửa; bản sửa sẽ được dùng khi kiểm chứng.
            </p>
          )}
          {compiled && compiled.assumptions.length > 0 && (
            <div className="border-t border-line pt-4">
              <p className="label mb-2">Giả định (hãy xác nhận)</p>
              <ul className="flex flex-wrap gap-2">
                {compiled.assumptions.map((a) => (
                  <li key={a.phrase} className="rounded-md border border-warn-line bg-warn-soft px-2.5 py-1 text-[0.8125rem] leading-5">
                    <span className="font-semibold">“{a.phrase}”</span> = {a.interpretation}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {compiled && compiled.unsupported_parts.length > 0 && (
            <Callout tone="warn" title="Phần chưa biểu diễn được:">
              <ul className="list-disc pl-5">
                {compiled.unsupported_parts.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </Callout>
          )}
        </div>
      </div>

      <div role="tabpanel" aria-labelledby={`${id}-json-tab`} hidden={tab !== "json"} className="p-4 sm:p-5">
        <label htmlFor={`${id}-json`} className="sr-only">
          Luật dạng JSON
        </label>
        <textarea
          id={`${id}-json`}
          value={jsonText}
          onChange={(e) => onJsonChange(e.target.value)}
          rows={14}
          spellCheck={false}
          className="field field-mono bg-sunken"
        />
      </div>
    </article>
  );
}
