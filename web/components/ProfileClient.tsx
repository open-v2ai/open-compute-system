"use client";

import { AlertCircle, Mail, Phone, ShieldCheck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isPublicDemo } from "@/lib/deployment";
import { api, money } from "@/lib/api";
import type { User } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

type IdentityType = "phone" | "email";
type IdentityAction = { type: IdentityType; mode: "bind" | "unbind" } | null;

export function ProfileClient() {
  const { t } = usePreferences();
  const [user, setUser] = useState<User | null>(null);
  const [action, setAction] = useState<IdentityAction>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<User>("/auth/me").then(setUser).catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function updateIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action) return;
    setBusy(true);
    setError("");
    setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      const updated = action.mode === "bind"
        ? await api<User>("/auth/identities", {
            method: "POST",
            body: JSON.stringify({
              [action.type]: data.get("identity"),
              current_password: data.get("current_password"),
            }),
          })
        : await api<User>(`/auth/identities/${action.type}`, {
            method: "DELETE",
            body: JSON.stringify({ current_password: data.get("current_password") }),
          });
      setUser(updated);
      setAction(null);
      setMessage(t(action.mode === "bind" ? "登录方式已绑定" : "登录方式已解绑"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("更新登录方式失败"));
    } finally {
      setBusy(false);
    }
  }

  function identityRow(type: IdentityType) {
    if (!user) return null;
    const value = user[type];
    const label = t(type === "phone" ? "手机号" : "邮箱");
    const Icon = type === "phone" ? Phone : Mail;
    const canUnbind = type === "phone" ? Boolean(user.email) : Boolean(user.phone);
    return (
      <div className="identity-row" key={type}>
        <div className="identity-row-main">
          <Icon size={19} />
          <div>
            <strong>{label}</strong>
            <div className="table-secondary">{value ?? t(type === "phone" ? "未绑定手机号" : "未绑定邮箱")}</div>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isPublicDemo() || (Boolean(value) && !canUnbind)}
          title={isPublicDemo() ? t("公开演示站不允许修改登录方式") : (Boolean(value) && !canUnbind ? t("至少保留一种登录方式") : undefined)}
          onClick={() => {
            setError("");
            setMessage("");
            setAction({ type, mode: value ? "unbind" : "bind" });
          }}
        >
          {t(value ? "解绑" : "增加绑定")}
        </Button>
      </div>
    );
  }

  return (
    <div className="workspace-content">
      <div className="workspace-title">
        <div><h1>{t("个人资料")}</h1><p>{t("管理基础资料、安全状态与登录方式。")}</p></div>
      </div>
      {error && <Alert variant="destructive"><AlertCircle /><AlertDescription>{error}</AlertDescription></Alert>}
      {message && <Alert><ShieldCheck /><AlertDescription>{message}</AlertDescription></Alert>}
      <Card className="panel">
        <div className="panel-head"><h2>{t("账户信息")}</h2><ShieldCheck size={20} /></div>
        <div className="connection-line"><span>{t("用户 ID")}</span><strong className="mono">{user?.id}</strong></div>
        <div className="connection-line"><span>{t("昵称")}</span><strong>{user?.nickname}</strong></div>
        <div className="connection-line"><span>{t("账户状态")}</span>{user && <StatusPill status={user.status} />}</div>
        <div className="connection-line"><span>{t("实名状态")}</span>{user && <StatusPill status={user.real_name_status} />}</div>
        <div className="connection-line"><span>{t("演示余额")}</span><strong>{money(user?.balance_cents ?? 0)}</strong></div>
      </Card>
      <Card className="panel">
        <div className="panel-head"><div><h2>{t("登录方式")}</h2><p className="table-secondary">{t("可同时绑定手机号和邮箱，业务数据始终归属上方用户 ID。")}</p></div></div>
        {identityRow("phone")}
        {identityRow("email")}
        {action && (
          <form className="identity-form" onSubmit={updateIdentity}>
            <h3>{t(action.mode === "bind" ? "增加" : "解绑")}{t(action.type === "phone" ? "手机号" : "邮箱")}</h3>
            {action.mode === "bind" && (
              <div className="form-row">
                <Label htmlFor="profile-identity">{t(action.type === "phone" ? "新手机号" : "新邮箱")}</Label>
                <Input id="profile-identity" name="identity" type={action.type === "email" ? "email" : "tel"} inputMode={action.type === "phone" ? "tel" : "email"} required />
              </div>
            )}
            <div className="form-row">
              <Label htmlFor="current-password">{t("当前密码")}</Label>
              <Input id="current-password" name="current_password" type="password" autoComplete="current-password" required />
            </div>
            <div className="identity-form-actions">
              <Button disabled={busy}>{t(busy ? "正在保存…" : "确认")}</Button>
              <Button type="button" variant="outline" onClick={() => setAction(null)}>{t("取消")}</Button>
            </div>
          </form>
        )}
      </Card>
      <Card className="panel">
        <Alert><AlertDescription>{t("当前换绑使用密码二次确认；生产上线前必须接入手机号和邮箱验证码，验证新登录方式的归属。")}</AlertDescription></Alert>
      </Card>
    </div>
  );
}
