"use client";

import { AdminLoginForm } from "@/components/AdminLoginForm";
import { PreferencesControls } from "@/components/PreferencesControls";
import { usePreferences } from "@/components/PreferencesProvider";
export default function AdminLoginPage(){const {t}=usePreferences();return <main className="auth-page auth-page-standalone"><div className="preferences-floating"><PreferencesControls/></div><section className="auth-story"><p className="eyebrow">INFERENCE CONTROL PLANE</p><h1>{t("模型、Token、端点，")}<br/>{t("一处运营。")}</h1><p>{t("高风险操作由服务端校验权限，并写入不可编辑的审计日志。")}</p></section><section className="auth-form-wrap"><AdminLoginForm/></section></main>}
