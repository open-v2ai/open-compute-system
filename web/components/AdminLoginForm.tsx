"use client";

import { AlertCircle, ArrowRight, FlaskConical, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { usePreferences } from "./PreferencesProvider";

const demoMode = process.env.NODE_ENV !== "production";

export function AdminLoginForm() {
  const { t } = usePreferences();
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api("/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: data.get("username"), password: data.get("password"), mfa_code: data.get("mfa") }),
      });
      router.push("/admin");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("登录失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <p className="eyebrow">INTERNAL OPERATIONS</p>
      <h2>{t("运营后台")}</h2>
      <p>{t("管理员账号与普通用户权限域分离。")}</p>
      <div className="form-row"><Label htmlFor="admin-user">{t("管理员账号")}</Label><Input id="admin-user" name="username" autoComplete="username" defaultValue={demoMode ? "admin" : undefined} required /></div>
      <div className="form-row"><Label htmlFor="admin-password">{t("密码")}</Label><Input id="admin-password" name="password" type="password" autoComplete="current-password" defaultValue={demoMode ? "Admin12345" : undefined} required /></div>
      <div className="form-row"><Label htmlFor="mfa">{t("MFA 验证码")}</Label><Input className="mono" id="mfa" name="mfa" inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={6} defaultValue={demoMode ? "123456" : undefined} required /></div>
      {error && <Alert variant="destructive"><AlertCircle /><AlertDescription>{error}</AlertDescription></Alert>}
      <Button variant="accent" className="w-full" disabled={busy}><ShieldCheck />{busy ? t("正在验证…") : <>{t("安全登录")} <ArrowRight /></>}</Button>
      {demoMode && <Alert variant="warning"><FlaskConical /><AlertTitle>{t("本地演示凭据")}</AlertTitle><AlertDescription>admin / Admin12345 / MFA 123456<br />{t("固定 MFA 仅在非生产环境有效。")}</AlertDescription></Alert>}
      <Button asChild variant="link" className="mx-auto"><Link href="/">{t("返回官网")}</Link></Button>
    </form>
  );
}
