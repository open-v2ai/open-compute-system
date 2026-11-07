"use client";

import { AlertCircle, ArrowRight, Info, Mail, Phone } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { usePreferences } from "./PreferencesProvider";

export function RegisterForm() {
  const { t } = usePreferences();
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [identityType, setIdentityType] = useState<"phone" | "email">("phone");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    if (data.get("password") !== data.get("confirm")) {
      setError(t("两次输入的密码不一致"));
      setBusy(false);
      return;
    }
    try {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          [identityType]: data.get("identity"), password: data.get("password"), nickname: data.get("nickname"),
          accepted_terms: data.get("terms") === "on",
        }),
      });
      router.push("/console");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("注册失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <p className="eyebrow">CREATE ACCOUNT</p>
      <h2>{t("创建算力账号")}</h2>
      <p>{t("完成注册后可获得演示额度。")}</p>
      <div className="identity-switch" aria-label={t("选择注册方式")}>
        <Button type="button" variant={identityType === "phone" ? "default" : "outline"} onClick={() => setIdentityType("phone")} aria-pressed={identityType === "phone"}><Phone />{t("手机号注册")}</Button>
        <Button type="button" variant={identityType === "email" ? "default" : "outline"} onClick={() => setIdentityType("email")} aria-pressed={identityType === "email"}><Mail />{t("邮箱注册")}</Button>
      </div>
      <div className="form-grid">
        <div className="form-row full"><Label htmlFor="reg-identity">{t(identityType === "phone" ? "手机号" : "邮箱")}</Label><Input key={identityType} id="reg-identity" name="identity" type={identityType === "email" ? "email" : "tel"} inputMode={identityType === "phone" ? "tel" : "email"} placeholder={identityType === "phone" ? t("11 至 15 位手机号") : "name@example.com"} required minLength={identityType === "phone" ? 11 : undefined} /></div>
        <div className="form-row full"><Label htmlFor="nickname">{t("昵称")}</Label><Input id="nickname" name="nickname" defaultValue={t("算力用户")} /></div>
        <div className="form-row"><Label htmlFor="reg-password">{t("密码")}</Label><Input id="reg-password" name="password" type="password" placeholder={t("字母 + 数字，8 位以上")} required minLength={8} /></div>
        <div className="form-row"><Label htmlFor="confirm">{t("确认密码")}</Label><Input id="confirm" name="confirm" type="password" required /></div>
      </div>
      <Alert><Info /><AlertDescription>{t("当前使用密码注册。生产上线前，手机号和邮箱绑定都必须接入验证码验证、摘要存储和频控。")}</AlertDescription></Alert>
      <Label className="check-row"><Checkbox name="terms" required />{t("我已阅读并同意服务协议、隐私政策与反挖矿协议")}</Label>
      {error && <Alert variant="destructive"><AlertCircle /><AlertDescription>{error}</AlertDescription></Alert>}
      <Button variant="accent" className="w-full" disabled={busy}>{busy ? t("正在注册…") : <>{t("注册并进入控制台")} <ArrowRight /></>}</Button>
      <p className="form-help" style={{ textAlign: "center" }}>{t("已有账号？")} <Link href="/login" style={{ color: "var(--blue)" }}>{t("直接登录")}</Link></p>
    </form>
  );
}
