import type { RuleRender } from "@/lib/types";

const EXEMPT = "miễn xác thực bổ sung";

/** Câu tiếng Việt sinh tất định từ AST; phần miễn xác thực tô đỏ (docs/07 mục 3.3). */
export function RuleSentence({ render, compact = false }: { render: RuleRender; compact?: boolean }) {
  const parts = render.then_vi.split(EXEMPT);
  return (
    <p className={compact ? "text-sm leading-6" : "text-base leading-7"}>
      <span className="font-semibold text-accent">NẾU</span> {render.when_vi}{" "}
      <span className="font-semibold text-accent">THÌ</span>{" "}
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 && (
            <mark className="rounded bg-red-100 px-1 font-semibold text-danger dark:bg-red-950">{EXEMPT}</mark>
          )}
        </span>
      ))}
    </p>
  );
}
