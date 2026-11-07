import { applicationPath } from "./deployment";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("X-Request-ID")) headers.set("X-Request-ID", crypto.randomUUID());
  if (!headers.has("Accept-Language")) headers.set("Accept-Language", currentLocale());
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfCookieName = process.env.NEXT_PUBLIC_CSRF_COOKIE || "ocs_csrf";
    const csrf = (typeof document === "undefined" ? "" : document.cookie)
      .split("; ")
      .find((item) => item.startsWith(`${csrfCookieName}=`))
      ?.split("=", 2)[1];
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  let response: Response;
  try {
    response = await fetch(`${applicationPath("/api/v1")}${path}`, {
      credentials: "include",
      ...init,
      headers,
    });
  } catch (caught) {
    if (
      typeof DOMException !== "undefined" &&
      caught instanceof DOMException &&
      caught.name === "AbortError"
    ) {
      throw new ApiError(0, "REQUEST_ABORTED", "请求已取消");
    }
    throw new ApiError(0, "NETWORK_ERROR", "无法连接服务器，请检查网络后重试");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail ?? {};
    const validationMessage = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join("；")
      : null;
    throw new ApiError(
      response.status,
      Array.isArray(detail) ? "VALIDATION_ERROR" : (detail.code ?? "REQUEST_FAILED"),
      validationMessage || detail.message || "请求失败",
    );
  }
  return body as T;
}

function currentLocale() {
  return typeof document === "undefined" ? "zh-CN" : document.documentElement.lang;
}

export function money(cents: number) {
  const sign = cents < 0 ? "-" : "";
  return `${sign}¥${(Math.abs(cents) / 100).toLocaleString(currentLocale(), { minimumFractionDigits: 2 })}`;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(currentLocale(), {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
