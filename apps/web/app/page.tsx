import { EnterSandbox } from "@/components/EnterSandbox";
import { HealthStatus } from "@/components/HealthStatus";
import { Logo } from "@/components/Logo";
import { VerdictBadge } from "@/components/VerdictBadge";
import { API_URL } from "@/lib/api";

const DEMOS: { n: number; screen: string; title: string; body: string; to: string; query: string; ready: boolean }[] = [
  {
    n: 1,
    screen: "Rule Studio",
    title: "Bắt lỗi chuyên viên bỏ sót",
    body: "Viết luật “khách thân thiết không cần xác thực thêm” — Z3 tìm ra giao dịch 10.000.001 đ lọt qua sinh trắc học.",
    to: "studio",
    query: "?demo=1",
    ready: true,
  },
  {
    n: 2,
    screen: "Policy Pack",
    title: "Quy định thay đổi",
    body: "Hạ ngưỡng sinh trắc học từ 10 triệu xuống 5 triệu: luật nào viết cứng con số sẽ bị chỉ ra kèm phản ví dụ.",
    to: "pack",
    query: "?demo=2",
    ready: true,
  },
  {
    n: 3,
    screen: "So sánh",
    title: "Chọn luật ít tổn thất nhất",
    body: "So sánh các phương án luật chống mule (cửa sổ 15/30/60 phút, giữ hay chặn) bằng tổn thất ròng (VNĐ) trên dữ liệu tổng hợp.",
    to: "compare",
    query: "?demo=3",
    ready: true,
  },
];

export default function Landing() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
        <Logo />
        <a href={`${API_URL}/docs`} className="btn btn-ghost btn-sm">
          Tài liệu API
        </a>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-4 pt-8 pb-16 md:px-6 md:pt-16">
        <section className="grid items-center gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:gap-14">
          <div className="space-y-6">
            <h1 className="text-[2.25rem] leading-[1.1] font-bold tracking-[-0.025em] text-balance md:text-[3.25rem]">
              Kiểm chứng luật chống gian lận trước khi bật
            </h1>
            <p className="max-w-[54ch] text-lg leading-8 text-muted text-pretty">
              Viết luật bằng tiếng Việt. Hệ thống chứng minh luật không phá quy định, tính tổn thất bằng VNĐ, và đề xuất bản sửa đã kiểm
              chứng.
            </p>
            <div className="flex flex-wrap items-start gap-x-5 gap-y-2">
              <EnterSandbox />
              <p className="pt-3 text-sm text-muted">Mỗi lần vào là một sandbox riêng, không cần đăng nhập.</p>
            </div>
          </div>

          <ProofPreview />
        </section>

        <section aria-labelledby="demos-title" className="space-y-4">
          <div>
            <h2 id="demos-title" className="section-title">
              Ba kịch bản để thử
            </h2>
            <p className="section-lede">Mỗi kịch bản mở thẳng màn hình tương ứng, đầu vào đã điền sẵn và có hướng dẫn từng bước.</p>
          </div>
          <ul className="grid gap-4 md:grid-cols-3">
            {DEMOS.map((d) => (
              <li key={d.title} className="panel flex flex-col gap-3 p-5">
                <p className="num text-[0.8125rem] text-muted">Demo {d.n}</p>
                <h3 className="text-[1.0625rem] font-semibold">{d.title}</h3>
                <p className="flex-1 text-sm leading-6 text-muted">{d.body}</p>
                {d.ready ? (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <EnterSandbox to={d.to} query={d.query} label="Thử ngay" variant="card" />
                    <span className="text-[0.8125rem] text-muted">mở {d.screen}</span>
                  </div>
                ) : (
                  <p className="text-sm text-muted">Đang xây dựng</p>
                )}
              </li>
            ))}
          </ul>
        </section>

        <footer className="grid gap-4 border-t border-line pt-8 md:grid-cols-[1fr_auto] md:items-start">
          <p className="max-w-[68ch] text-sm leading-6 text-muted">
            Dùng được như công cụ thật: nhập bộ luật JSON của bạn ở màn Bộ luật, hoặc gọi thẳng{" "}
            <a href={`${API_URL}/docs`} className="link">
              API công khai /verify và /backtest
            </a>{" "}
            (có ví dụ curl, không cần đăng nhập).
          </p>
          <HealthStatus />
        </footer>
      </main>
    </div>
  );
}

/** Minh họa tĩnh lấy đúng kết quả của Demo 1 (luật, kết luận, phản ví dụ) — không phải số liệu bịa. */
function ProofPreview() {
  return (
    <figure className="panel overflow-hidden">
      <figcaption className="flex items-center justify-between gap-3 border-b border-line bg-sunken px-4 py-2.5 text-[0.8125rem] text-muted">
        <span>Ví dụ: kết quả Demo 1</span>
        <span className="font-mono">DRAFT-0001</span>
      </figcaption>
      <div className="space-y-4 p-4 sm:p-5">
        <p className="text-[0.9375rem] leading-7">
          <span className="mr-1 font-mono text-[0.8em] font-semibold text-accent">NẾU</span>
          tuổi tài khoản gửi lớn hơn 365 ngày VÀ người nhận quen{" "}
          <span className="mr-1 font-mono text-[0.8em] font-semibold text-accent">THÌ</span>
          <mark className="rounded-sm bg-fail-soft px-1 font-semibold text-fail">
            miễn xác thực bổ sung
          </mark>
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <VerdictBadge verdict="FAIL" />
          <span className="text-sm font-medium">Vi phạm INV-AUTH-01</span>
        </div>
        <div className="rounded-lg border border-line bg-surface">
          <div className="px-4 pt-3 pb-2">
            <p className="text-[0.8125rem] text-muted">Giao dịch phản ví dụ (do hệ thống tìm)</p>
            <p className="num text-[2.25rem] leading-tight font-bold tracking-tight">10.000.001 đ</p>
          </div>
          <div className="mx-4 flex flex-wrap items-center justify-between gap-2 border-t border-dashed border-line-strong py-3 text-sm">
            <span className="text-muted">Bộ luật cho kết quả</span>
            <span className="font-semibold text-fail line-through decoration-2">Cho qua · không xác thực thêm</span>
          </div>
        </div>
      </div>
    </figure>
  );
}
