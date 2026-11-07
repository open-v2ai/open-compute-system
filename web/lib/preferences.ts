export const locales = ["zh-CN", "en-US"] as const;
export const themes = ["light", "dark"] as const;

export type Locale = (typeof locales)[number];
export type Theme = (typeof themes)[number];

export const defaultLocale: Locale = "zh-CN";
export const defaultTheme: Theme = "light";

export function parseLocale(value: string | undefined): Locale {
  return locales.includes(value as Locale) ? (value as Locale) : defaultLocale;
}

export function parseTheme(value: string | undefined): Theme {
  return themes.includes(value as Theme) ? (value as Theme) : defaultTheme;
}
