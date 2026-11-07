import { describe, expect, it } from "vitest";
import { safeExternalUrl, safeInternalPath } from "../lib/security";
import { money } from "../lib/api";

describe("safeInternalPath", () => {
  it("accepts same-site paths with query parameters", () => {
    expect(safeInternalPath("/console/create?sku=sku_1", "/console")).toBe(
      "/console/create?sku=sku_1",
    );
  });

  it("rejects absolute, protocol-relative, mixed-slash, and control-character targets", () => {
    expect(safeInternalPath("https://evil.example", "/console")).toBe("/console");
    expect(safeInternalPath("//evil.example", "/console")).toBe("/console");
    expect(safeInternalPath("/\\evil.example", "/console")).toBe("/console");
    expect(safeInternalPath("/console\nLocation:https://evil.example", "/console")).toBe(
      "/console",
    );
  });
});

describe("safeExternalUrl", () => {
  it("only permits HTTPS URLs", () => {
    expect(safeExternalUrl("https://jupyter.example/session")).toBe(
      "https://jupyter.example/session",
    );
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("http://jupyter.example/session")).toBeNull();
  });
});

describe("money", () => {
  it("places the sign before the currency symbol", () => {
    expect(money(-248)).toBe("-¥2.48");
  });
});
