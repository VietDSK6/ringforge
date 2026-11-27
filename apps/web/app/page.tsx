import { EnterSandbox } from "@/components/EnterSandbox";
import { HealthStatus } from "@/components/HealthStatus";

const DEMOS = [
  {
    title: "Bắt lỗi chuyên viên bỏ sót",
    body: "Viết luật “khách thân thiết không cần xác thực thêm” — Z3 tìm ra giao dịch 10.000.001 đ lọt qua sinh trắc học.",
    to: "studio",
    query: "?demo=1",
    ready: true,
  },
  {
    title: "Quy định thay đổi",
    body: "Hạ ngưỡng sinh trắc học từ 10 triệu xuống 5 triệu: luật nào viết cứng con số sẽ bị chỉ ra kèm phản ví dụ.",
    to: "pack",
    query: "?demo=2",
    ready: true,
  },
  {
    title: "Chọn luật ít tổn thất nhất",
    body: "So sánh các phương án luật chống mule bằng tổn thất ròng (VNĐ) trên dữ liệu tổng hợp.",
    ready: false,
  },
];

export default function Landing() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-4 py-12 md:py-20">
      <header className="max-w-3xl space-y-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">RingForge</p>
        <h1 className="text-3xl font-bold tracking-tight text-balance md:text-5xl">
          Kiểm chứng luật chống gian lận trước khi bật
        </h1>
        <p className="text-lg text-muted text-pretty">
          Viết luật bằng tiếng Việt. Hệ thống chứng minh luật không phá quy định, tính tổn thất bằng VNĐ, và đề xuất bản
          sửa đã kiểm chứng.
        </p>
        <EnterSandbox />
      </header>

      <section aria-labelledby="demos-title" className="space-y-4">
        <h2 id="demos-title" className="text-lg font-semibold">
          Ba kịch bản để thử
        </h2>
        <ul className="grid gap-4 md:grid-cols-3">
          {DEMOS.map((d) => (
            <li key={d.title} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
              <h3 className="font-semibold">{d.title}</h3>
              <p className="flex-1 text-sm text-muted">{d.body}</p>
              {d.ready ? (
                <EnterSandbox to={d.to} query={d.query} label="Thử ngay" variant="card" />
              ) : (
                <p className="text-sm text-muted">Đang xây dựng</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <footer className="max-w-md">
        <HealthStatus />
      </footer>
    </main>
  );
}
