"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { translate } from "@/lib/messages";
import { applicationBasePath } from "@/lib/deployment";
import type { Locale, Theme } from "@/lib/preferences";

type PreferencesContextValue = {
  locale: Locale;
  theme: Theme;
  setLocale: (locale: Locale) => void;
  setTheme: (theme: Theme) => void;
  t: (source: string) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function persist(name: "locale" | "theme", value: string) {
  localStorage.setItem(`ocs_${name}`, value);
  document.cookie = `ocs_${name}=${encodeURIComponent(value)}; Path=${applicationBasePath() || "/"}; Max-Age=31536000; SameSite=Lax`;
}

export function PreferencesProvider({
  children,
  initialLocale,
  initialTheme,
}: {
  children: ReactNode;
  initialLocale: Locale;
  initialTheme: Theme;
}) {
  const [theme, setThemeState] = useState(initialTheme);

  const setLocale = useCallback((locale: Locale) => {
    persist("locale", locale);
    document.documentElement.lang = locale;
    document.documentElement.dataset.locale = locale;
    window.location.reload();
  }, []);

  const setTheme = useCallback((theme: Theme) => {
    persist("theme", theme);
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    setThemeState(theme);
  }, []);

  const t = useCallback((source: string) => translate(initialLocale, source), [initialLocale]);

  const value = useMemo<PreferencesContextValue>(() => ({
    locale: initialLocale,
    theme,
    setLocale,
    setTheme,
    t,
  }), [initialLocale, theme, setLocale, setTheme, t]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error("usePreferences must be used within PreferencesProvider");
  return value;
}
