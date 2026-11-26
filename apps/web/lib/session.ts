// Ghi nhớ phiên sandbox gần nhất trong trình duyệt (chỉ là tiện ích; mất cũng không sao).
const KEY = "rf.sid";

export function rememberSession(sid: string) {
  try {
    localStorage.setItem(KEY, sid);
  } catch {
    /* chế độ riêng tư / bị chặn lưu trữ */
  }
}

export function lastSession(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function forgetSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* bỏ qua */
  }
}
