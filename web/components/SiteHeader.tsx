"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { isPublicDemo } from "@/lib/deployment";
import { Brand } from "./Brand";
import { PreferencesControls } from "./PreferencesControls";
import { usePreferences } from "./PreferencesProvider";

const links = [
  ["模型 API", "/models"],
  ["算力市场", "/market"],
  ["使用指南", "/guide"],
] as const;

export function SiteHeader() {
  const { locale, t } = usePreferences();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const nav = links.map(([label, href]) => (
    <Link
      key={href}
      className={`nav-link ${path === href ? "active" : ""}`}
      href={href}
      onClick={() => setOpen(false)}
    >
      {label === "使用指南" ? (locale === "en-US" ? "Guide" : label) : t(label)}
    </Link>
  ));
  return (
    <>
      <header className="site-header">
        <div className="container nav-inner">
          <Brand />
          <nav className="nav-links" aria-label={t("主导航")}>
            {nav}
          </nav>
          <div className="nav-actions">
            <PreferencesControls />
            <Link className="nav-link nav-login" href="/login">
              {t("登录")}
            </Link>
            <Button asChild variant="accent" size="sm">
              <Link href="/console">{t("控制台")}</Link>
            </Button>
            <Button className="mobile-toggle" variant="ghost" size="icon-sm" aria-label={t("切换导航")} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}>
              {open ? <X size={22} /> : <Menu size={22} />}
            </Button>
          </div>
        </div>
      </header>
      {open && (
        <nav id="mobile-navigation" className="mobile-nav" aria-label={t("移动导航")}>
          {nav}
          <Button asChild><Link href="/login">{t(isPublicDemo() ? "登录" : "登录 / 注册")}</Link></Button>
        </nav>
      )}
    </>
  );
}
