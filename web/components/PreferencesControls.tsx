"use client";

import { Languages, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePreferences } from "./PreferencesProvider";

export function PreferencesControls({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale, theme, setTheme, t } = usePreferences();
  const nextLocale = locale === "zh-CN" ? "en-US" : "zh-CN";
  const nextTheme = theme === "light" ? "dark" : "light";
  const localeLabel = t(nextLocale === "en-US" ? "切换到英文" : "切换到中文");
  const themeLabel = t(nextTheme === "dark" ? "切换到深色主题" : "切换到浅色主题");

  return (
    <div className="preferences-controls" aria-label={t("切换语言")}>
      <Button
        className="preference-button"
        variant="ghost"
        size={compact ? "icon-sm" : "sm"}
        type="button"
        aria-label={localeLabel}
        title={localeLabel}
        onClick={() => setLocale(nextLocale)}
      >
        <Languages size={17} />
      </Button>
      <Button
        className="preference-button"
        variant="ghost"
        size="icon-sm"
        type="button"
        aria-label={themeLabel}
        title={themeLabel}
        onClick={() => setTheme(nextTheme)}
      >
        {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
      </Button>
    </div>
  );
}
