import type { Metadata } from "next";
import { cookies } from "next/headers";
import { PreferencesProvider } from "@/components/PreferencesProvider";
import { parseLocale, parseTheme } from "@/lib/preferences";
import { applicationPath } from "@/lib/deployment";
import "./globals.css";

// A per-request CSP nonce cannot be embedded safely in statically generated HTML.
export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const locale = parseLocale((await cookies()).get("ocs_locale")?.value);
  return {
    title: { default: "Open Compute System", template: "%s · Open Compute System" },
    description: locale === "en-US"
      ? "Self-hosted AI inference commerce infrastructure for GPUs, model APIs, keys, and token metering."
      : "自托管 AI 推理商业化基础设施：GPU 纳管、模型 API、Key 与 Token 计量计费。",
    icons: { icon: applicationPath("/icon.svg") },
  };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = await cookies();
  const locale = parseLocale(cookieStore.get("ocs_locale")?.value);
  const theme = parseTheme(cookieStore.get("ocs_theme")?.value);
  return (
    <html
      lang={locale}
      data-locale={locale}
      data-theme={theme}
      data-scroll-behavior="smooth"
      style={{ colorScheme: theme }}
      suppressHydrationWarning
    >
      <body>
        <PreferencesProvider initialLocale={locale} initialTheme={theme}>
          {children}
        </PreferencesProvider>
      </body>
    </html>
  );
}
