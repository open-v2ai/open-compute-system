"use client";

import { Suspense } from "react";
import { LoginForm } from "@/components/LoginForm";
import { PublicDemoNotice } from "@/components/PublicDemoNotice";
import { SiteHeader } from "@/components/SiteHeader";
import { usePreferences } from "@/components/PreferencesProvider";

export default function LoginPage() {
  const { t } = usePreferences();
  return <><SiteHeader /><PublicDemoNotice /><main className="auth-page"><section className="auth-story"><p className="eyebrow">OPEN COMPUTE SYSTEM CONSOLE</p><h1>{t("从一个 API Key，")}<br />{t("开始调用模型。")}</h1><p>{t("模型、Token、额度和 GPU 实例保持一条清晰链路。")}</p></section><section className="auth-form-wrap"><Suspense fallback={<div>{t("正在加载…")}</div>}><LoginForm /></Suspense></section></main></>;
}
