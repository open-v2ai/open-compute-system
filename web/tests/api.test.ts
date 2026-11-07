import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("api", () => {
  it.each([
    ["", "default-token"],
    ["ocs_preview_csrf", "preview-token"],
  ])("sends the CSRF token for the configured deployment cookie %s", async (name, expected) => {
    vi.stubEnv("NEXT_PUBLIC_CSRF_COOKIE", name);
    vi.stubGlobal("document", {
      cookie: "ocs_csrf=default-token; ocs_preview_csrf=preview-token",
      documentElement: { lang: "zh-CN" },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/resource", { method: "POST" });
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(request.headers).get("X-CSRF-Token")).toBe(expected);
  });

  it("preserves explicit request headers and does not label GET requests as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api("/health", {
      headers: { "X-Request-ID": "req_explicit", "Accept-Language": "en-US" },
    });

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(request.headers);
    expect(headers.get("X-Request-ID")).toBe("req_explicit");
    expect(headers.get("Accept-Language")).toBe("en-US");
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("adds JSON content type for serialized request bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api("/resource", { method: "POST", body: JSON.stringify({ name: "test" }) });

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(request.headers).get("Content-Type")).toBe("application/json");
  });

  it("maps transport failures to a stable API error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    await expect(api("/health")).rejects.toEqual(
      expect.objectContaining({
        status: 0,
        code: "NETWORK_ERROR",
        message: "无法连接服务器，请检查网络后重试",
      }),
    );
  });
});
