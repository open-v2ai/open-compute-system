"use client";

import { AlertCircle, ArrowRight, FlaskConical, Mail, Phone } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { isPublicDemo } from "@/lib/deployment";
import { safeInternalPath } from "@/lib/security";
import { usePreferences } from "./PreferencesProvider";

const demoMode = process.env.NODE_ENV !== "production" || isPublicDemo();

export function LoginForm() {
  const { t } = usePreferences();
  const router = useRouter();
  const search = useSearchParams();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [identityType, setIdentityType] = useState<"phone" | "email">("phone");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          [identityType]: data.get("identity"),
          password: data.get("password"),
        }),
      });
      router.push(safeInternalPath(search.get("next"), "/console"));
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("登录失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <p className="eyebrow">WELCOME BACK</p>
      <h2>{t("登录控制台")}</h2>
      <p>{t("管理 API Key、Token 用量和 GPU 实例。")}</p>
      <div className="identity-switch" aria-label={t("选择登录方式")}>
        <Button type="button" variant={identityType === "phone" ? "default" : "outline"} onClick={() => setIdentityType("phone")} aria-pressed={identityType === "phone"}><Phone />{t("手机号")}</Button>
        <Button type="button" variant={identityType === "email" ? "default" : "outline"} onClick={() => setIdentityType("email")} aria-pressed={identityType === "email"}><Mail />{t("邮箱")}</Button>
      </div>
      <div className="form-row">
        <Label htmlFor="identity">{t(identityType === "phone" ? "手机号" : "邮箱")}</Label>
        <Input key={identityType} id="identity" name="identity" type={identityType === "email" ? "email" : "tel"} inputMode={identityType === "phone" ? "tel" : "email"} autoComplete="username" defaultValue={demoMode ? (identityType === "phone" ? "13800138000" : "demo@opencompute.local") : undefined} required />
      </div>
      <div className="form-row">
        <Label htmlFor="password">{t("密码")}</Label>
        <Input id="password" name="password" type="password" autoComplete="current-password" defaultValue={demoMode ? "Demo12345" : undefined} required />
      </div>
      {error && <Alert variant="destructive"><AlertCircle/><AlertDescription>{error}</AlertDescription></Alert>}
      <Button variant="accent" className="w-full" disabled={busy}>
        {busy ? t("正在登录…") : <>{t("登录")} <ArrowRight /></>}
      </Button>
      {demoMode && (
        <Alert variant="warning">
          <FlaskConical />
          <AlertTitle>{t("演示账号")}</AlertTitle>
          <AlertDescription>{t("手机号 13800138000 或邮箱 demo@opencompute.local")}<br />{t("密码 Demo12345")}</AlertDescription>
        </Alert>
      )}
      {!isPublicDemo() && <p className="form-help" style={{ textAlign: "center" }}>{t("还没有账号？")} <Link href="/register" style={{ color: "var(--blue)" }}>{t("立即注册")}</Link></p>}
    </form>
  );
}
