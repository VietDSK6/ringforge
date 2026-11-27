import { EnterSandbox } from "@/components/EnterSandbox";
import { HealthStatus } from "@/components/HealthStatus";
import { Logo } from "@/components/Logo";
import { API_URL } from "@/lib/api";

const DEMOS: { n: number; screen: string; title: string; body: string; to: string; query: string; ready: boolean }[] = [
  {
    n: 1,
    screen: "Rule Studio",
    title: "Bắt lỗi chuyên viên bỏ sót",
    body: "Viết luật “khách thân thiết không cần xác thực thêm” — Z3 tìm ra giao dịch 10.000.001 đ lọt qua sinh trắc học. Phần 2: lỗ hổng mà dữ liệu cũ không có.",
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
            <p className="max-w-[56ch] text-lg leading-8 text-pretty">
              Luật chống gian lận cũng là code. Viết sai một điều kiện là kẻ gian lọt qua hoặc vi phạm quy định, và thường chỉ biết khi
              đã mất tiền.
            </p>
            <p className="max-w-[56ch] text-lg leading-8 text-muted text-pretty">
              Viết luật bằng tiếng Việt. Hệ thống chứng minh luật không phá quy định, tính tổn thất bằng VNĐ, và đề xuất bản sửa đã kiểm
              chứng.
            </p>
            <div className="flex flex-wrap items-start gap-3">
              <EnterSandbox query="?demo=1&auto=1" label="Xem demo 60 giây" />
              <EnterSandbox label="Vào sandbox" variant="card" />
            </div>
            <p className="text-sm text-muted">
              Demo tự chạy, có lời dẫn; bấm “Dừng” bất cứ lúc nào để tự thử. Không cần đăng nhập.
            </p>
          </div>

          <ProofPreview />
        </section>

        <section aria-labelledby="why-title" className="grid gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-2">
          <h2 id="why-title" className="sr-only">
            Khác gì cách test thông thường
          </h2>
          <div className="bg-surface p-5">
            <p className="text-sm text-muted">Cách thường làm: chạy thử luật trên dữ liệu cũ</p>
            <p className="mt-1 text-lg font-semibold">Chỉ thấy lỗi đã từng xảy ra.</p>
            <p className="mt-1 text-sm leading-6 text-muted">Lỗ hổng chưa ai khai thác thì dữ liệu cũ không có, nên test vẫn “xanh”.</p>
          </div>
          <div className="bg-surface p-5">
            <p className="text-sm text-muted">RingForge: kiểm chứng hình thức bằng Z3</p>
            <p className="mt-1 text-lg font-semibold">Xét mọi giao dịch có thể có, kể cả chưa từng xảy ra.</p>
            <p className="mt-1 text-sm leading-6 text-muted">Có lỗ hổng thì chỉ ra một giao dịch cụ thể, trước khi luật được bật.</p>
          </div>
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

/**
 * Minh họa tĩnh lấy đúng kết quả của Demo 1 phần 2 (luật, kết luận, phản ví dụ, số giao dịch trong dữ liệu) — không phải số bịa.
 * Nếu dữ liệu seed hoặc Policy Pack seed đổi, kiểm lại bằng /verify rồi cập nhật.
 */
function ProofPreview() {
  return (
    <figure className="panel overflow-hidden">
      <figcaption className="flex items-center justify-between gap-3 border-b border-line bg-sunken px-4 py-2.5 text-[0.8125rem] text-muted">
        <span>Ví dụ: Demo 1, phần 2</span>
        <span className="font-mono">DRAFT-0001</span>
      </figcaption>
      <div className="space-y-4 p-4 sm:p-5">
        <p className="text-[0.9375rem] leading-7">
          <span className="mr-1 font-mono text-[0.8em] font-semibold text-accent">NẾU</span>
          kênh là thanh toán QR VÀ người nhận là merchant đã xác minh{" "}
          <span className="mr-1 font-mono text-[0.8em] font-semibold text-accent">THÌ</span>
          <mark className="rounded-sm bg-fail-soft px-1 font-semibold text-fail">miễn xác thực bổ sung</mark>
        </p>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line text-sm">
          <div className="bg-surface p-3">
            <p className="text-[0.8125rem] text-muted">Chạy thử trên 6 ngày dữ liệu</p>
            <p className="mt-0.5 font-semibold">0 giao dịch vi phạm</p>
          </div>
          <div className="bg-surface p-3">
            <p className="text-[0.8125rem] text-muted">Kiểm chứng Z3</p>
            <p className="mt-0.5 font-semibold text-fail">Có lỗ hổng</p>
          </div>
        </div>
        <div className="rounded-md border border-line bg-surface">
          <div className="px-4 pt-3 pb-2">
            <p className="text-[0.8125rem] text-muted">Thanh toán QR do Z3 tìm ra</p>
            <p className="num text-[2.25rem] leading-tight font-bold tracking-tight">10.000.001 đ</p>
          </div>
          <div className="mx-4 flex flex-wrap items-baseline justify-between gap-2 border-t border-dashed border-line-strong py-3 text-sm">
            <span className="text-muted">Bộ luật cho kết quả</span>
            <span className="font-semibold text-fail">Cho qua · không xác thực thêm</span>
          </div>
        </div>
        <p className="text-sm leading-6 text-muted">
          Trong dữ liệu chưa có giao dịch nào như vậy, nên test thường vẫn “xanh”. Kẻ gian thì có thể tạo ra nó.
        </p>
      </div>
    </figure>
  );
}
