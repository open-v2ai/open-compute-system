import { describe, expect, it } from "vitest";
import { translate } from "../lib/messages";
import { defaultLocale, defaultTheme, parseLocale, parseTheme } from "../lib/preferences";

describe("display preferences", () => {
  it("accepts supported locale and theme values", () => {
    expect(parseLocale("en-US")).toBe("en-US");
    expect(parseTheme("dark")).toBe("dark");
  });

  it("falls back safely for unknown cookie values", () => {
    expect(parseLocale("fr-FR")).toBe(defaultLocale);
    expect(parseTheme("system")).toBe(defaultTheme);
  });

  it("uses Chinese source strings as the default and English messages when selected", () => {
    expect(translate("zh-CN", "控制台")).toBe("控制台");
    expect(translate("en-US", "控制台")).toBe("Console");
  });
});
