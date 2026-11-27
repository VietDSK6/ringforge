import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cho phép chạy song song một dev server thứ hai (thư mục build riêng), ví dụ khi một phiên khác đang giữ .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
