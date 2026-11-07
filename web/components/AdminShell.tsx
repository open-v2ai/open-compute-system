"use client";

import { Activity, CircleUserRound, FileClock, LayoutDashboard, LoaderCircle, LogOut, PackageSearch, ReceiptText, ServerCog, Sparkles, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Admin } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Brand } from "./Brand";
import { PreferencesControls } from "./PreferencesControls";
import { usePreferences } from "./PreferencesProvider";

const nav=[
  ["经营看板","/admin",LayoutDashboard,"dashboard.read"],["模型 API 运营","/admin/inference",Sparkles,"inference.read"],["资源来源","/admin/resources",ServerCog,"providers.read"],["GPU SKU 与库存","/admin/catalog",PackageSearch,"catalog.read"],["实例与任务","/admin/instances",Activity,"instances.read"],["用户管理","/admin/users",Users,"users.read"],["订单财务","/admin/orders",ReceiptText,"orders.read"],["审计日志","/admin/audit",FileClock,"audit.read"],
] as const;

export function AdminShell({children}:{children:React.ReactNode}){
  const {t}=usePreferences();
  const path=usePathname();const router=useRouter();const[admin,setAdmin]=useState<Admin|null>(null);const[loading,setLoading]=useState(path!=="/admin/login");
  useEffect(()=>{if(path==="/admin/login")return;api<Admin>("/admin/auth/me").then(setAdmin).catch(()=>router.replace("/admin/login")).finally(()=>setLoading(false));},[path,router]);
  async function logout(){await api("/auth/logout",{method:"POST"});router.push("/admin/login");router.refresh();}
  if(path==="/admin/login")return <>{children}</>;
  if(loading)return <div className="auth-form-wrap" style={{minHeight:"100vh"}}><div className="mono" role="status"><LoaderCircle className="animate-spin" size={20}/> {t("正在加载运营后台…")}</div></div>;
  if(!admin)return null;
  return <div className="admin-shell"><aside className="sidebar"><Brand href="/admin"/><p className="side-label">{t("运营管理后台")}</p>{nav.filter(([, , ,permission])=>admin.permissions.includes(permission)).map(([label,href,Icon])=><Link className={`side-link ${path===href?"active":""}`} href={href} key={href} title={t(label)} aria-label={t(label)} aria-current={path===href?"page":undefined}><Icon size={18}/><span>{t(label)}</span></Link>)}<div className="side-footer"><div>{admin.display_name}</div><div>{admin.role}</div><Button variant="ghost" size="sm" onClick={logout}><LogOut size={14}/>{t("退出后台")}</Button></div></aside><main className="admin-main"><header className="workspace-top"><strong>{t("运营管理后台")}</strong><div className="workspace-actions"><PreferencesControls compact/><Badge variant="success">{t("内部访问")}</Badge><CircleUserRound aria-hidden="true" size={20}/></div></header>{children}</main></div>;
}
