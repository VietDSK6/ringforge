import type { RuleRender } from "@/lib/types";

const EXEMPT = "miễn xác thực bổ sung";

/** Câu tiếng Việt sinh tất định từ AST; phần miễn xác thực tô đỏ (docs/07 mục 3.3). */
export function RuleSentence({ render, compact = false }: { render: RuleRender; compact?: boolean }) {
  const parts = render.then_vi.split(EXEMPT);
  const kw = "mr-1 font-mono text-[0.8em] font-semibold tracking-wide text-accent";
  return (
    <p className={compact ? "text-sm leading-6" : "text-[1.0625rem] leading-7"}>
      <span className={kw}>NẾU</span>
      {render.when_vi} <span className={kw}>THÌ</span>
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 && (
            <mark className="rounded-sm bg-fail-soft px-1 font-semibold text-fail underline decoration-fail-line decoration-2 underline-offset-4">
              {EXEMPT}
            </mark>
          )}
        </span>
      ))}
    </p>
  );
}
