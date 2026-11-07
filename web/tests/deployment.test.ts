import { afterEach, describe, expect, it, vi } from "vitest";
import { applicationPath, exampleApiBaseUrl, withoutBasePath } from "../lib/deployment";
import { safeInternalPath } from "../lib/security";

afterEach(() => vi.unstubAllEnvs());

describe("subpath deployment", () => {
  it("retains root deployment URLs by default", () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "");
    expect(applicationPath("/api/v1/auth/me")).toBe("/api/v1/auth/me");
  });

  it("prefixes fetch and example URLs while preserving internal navigation", () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/open-compute-system");
    vi.stubEnv("NEXT_PUBLIC_DEMO_ORIGIN", "https://demo.v2ai.org");
    expect(applicationPath("/api/v1/auth/me")).toBe("/open-compute-system/api/v1/auth/me");
    expect(exampleApiBaseUrl()).toBe("https://demo.v2ai.org/open-compute-system/api/v1");
    expect(withoutBasePath("/open-compute-system/console?sku=one"))
      .toBe("/console?sku=one");
    expect(safeInternalPath("/open-compute-system/console?sku=one", "/console"))
      .toBe("/console?sku=one");
    expect(withoutBasePath("/open-compute-system-other/console"))
      .toBe("/open-compute-system-other/console");
  });

  it("still rejects protocol-relative paths after prefix removal", () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/open-compute-system");
    expect(safeInternalPath("/open-compute-system//evil.example", "/console"))
      .toBe("/console");
    expect(safeInternalPath("/open-compute-system/\\evil.example", "/console"))
      .toBe("/console");
  });
});
