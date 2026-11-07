"use client";

import { Users } from "lucide-react";
import { useEffect,useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api,formatDate,money } from "@/lib/api";
import type { AdminUserRow } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function AdminUsers(){
  const{t}=usePreferences();
  const[users,setUsers]=useState<AdminUserRow[]>([]); const[error,setError]=useState("");
  useEffect(()=>{api<AdminUserRow[]>("/admin/users").then(setUsers).catch((e)=>setError(e.message))},[]);
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("用户管理")}</h1><p>{t("登录方式默认脱敏；业务归属统一使用用户 ID。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Card className="panel"><div className="panel-head"><h2>{t("用户列表")}</h2><Users size={20}/></div><div className="table-wrap"><table className="data-table"><thead><tr><th>{t("用户")}</th><th>{t("登录方式")}</th><th>{t("实名")}</th><th>{t("余额")}</th><th>{t("状态")}</th><th>{t("注册时间")}</th></tr></thead><tbody>{users.map(user=><tr key={user.id}><td><div className="table-primary">{user.nickname}</div><div className="table-secondary mono">{user.id}</div></td><td><div>{user.phone??t("未绑定手机号")}</div><div className="table-secondary">{user.email??t("未绑定邮箱")}</div></td><td><StatusPill status={user.real_name_status}/></td><td>{user.balance_cents===null?t("无权限"):money(user.balance_cents)}</td><td><StatusPill status={user.status}/></td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div></Card></div>;
}
