"use client";

import { RegisterForm } from "@/components/RegisterForm";
import { SiteHeader } from "@/components/SiteHeader";
import { usePreferences } from "@/components/PreferencesProvider";

export default function RegisterPage(){const {t}=usePreferences();return <><SiteHeader/><main className="auth-page"><section className="auth-story"><p className="eyebrow">START SMALL</p><h1>{t("从一张卡开始，")}<br />{t("把想法跑起来。")}</h1><p>{t("真实支付未接入前，注册用户获得可用于 MockProvider 的演示额度。")}</p></section><section className="auth-form-wrap"><RegisterForm/></section></main></>}
