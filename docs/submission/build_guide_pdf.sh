#!/usr/bin/env bash
# Xuất hướng dẫn 1 trang A4 thành PDF sau khi có link production.
#   WEB_URL=https://ringforge.vercel.app API_URL=https://ringforge-api.onrender.com CONTACT="email đội" \
#     docs/submission/build_guide_pdf.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
: "${WEB_URL:?Đặt WEB_URL}" "${API_URL:?Đặt API_URL}" "${CONTACT:?Đặt CONTACT}"
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
tmp="$(mktemp -d)/huong-dan.html"
python3 - "$here/huong-dan-1-trang.html" "$tmp" <<'PY'
import os, sys
s = open(sys.argv[1], encoding="utf-8").read()
for k in ("WEB_URL", "API_URL", "CONTACT"):
    s = s.replace("{{%s}}" % k, os.environ[k].rstrip("/"))
open(sys.argv[2], "w", encoding="utf-8").write(s)
PY
"$chrome" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$here/RingForge-huong-dan.pdf" "file://$tmp"
echo "Đã ghi $here/RingForge-huong-dan.pdf"
