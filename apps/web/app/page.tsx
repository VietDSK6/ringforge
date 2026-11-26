import { HealthStatus } from "@/components/HealthStatus";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">RingForge</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          CI/CD cho chính sách rủi ro: kiểm chứng hình thức bộ luật chống gian lận trước khi bật.
        </p>
      </div>
      <HealthStatus />
    </main>
  );
}
