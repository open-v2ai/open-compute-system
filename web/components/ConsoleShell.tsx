"use client";

import { Activity, CircleUserRound, KeyRound, LayoutDashboard, LoaderCircle, LogOut, Plus, ReceiptText, Server } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isPublicDemo } from "@/lib/deployment";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PublicDemoNotice } from "./PublicDemoNotice";
import { Brand } from "./Brand";
import { PreferencesControls } from "./PreferencesControls";
import { usePreferences } from "./PreferencesProvider";

const demoMode = process.env.NODE_ENV !== "production" || isPublicDemo();
const nav = [
  ["概览", "/console", LayoutDashboard],
  ["API Keys", "/console/keys", KeyRound],
  ["Token 用量", "/console/usage", Activity],
  ["创建实例", "/console/create", Plus],
  ["容器实例", "/console/instances", Server],
  ["我的订单", "/console/orders", ReceiptText],
  ["个人资料", "/console/profile", CircleUserRound],
] as const;

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const { t } = usePreferences();
  const path = usePathname(); const router = useRouter();
  const [user,setUser]=useState<User|null>(null); const [loading,setLoading]=useState(true);
  useEffect(()=>{api<User>("/auth/me").then(setUser).catch(()=>{const target=`${window.location.pathname}${window.location.search}`;router.replace(`/login?next=${encodeURIComponent(target)}`)}).finally(()=>setLoading(false))},[path,router]);
  async function logout(){await api("/auth/logout",{method:"POST"});router.push("/");router.refresh()}
  if(loading)return <div className="auth-form-wrap" style={{minHeight:"100vh"}}><div className="mono" role="status"><LoaderCircle className="animate-spin" size={20}/> {t("正在加载控制台…")}</div></div>;
  if(!user)return null;
  return <div className="console-shell"><aside className="sidebar"><Brand href="/"/><p className="side-label">{t("API 与算力控制台")}</p>{nav.map(([label,href,Icon])=><Link className={`side-link ${path===href?"active":""}`} href={href} key={href} title={t(label)} aria-label={t(label)} aria-current={path===href?"page":undefined}><Icon size={18}/><span>{t(label)}</span></Link>)}<div className="side-footer"><div>{user.nickname}</div><Button variant="ghost" size="sm" onClick={logout}><LogOut size={14}/>{t("退出登录")}</Button></div></aside><main className="console-main"><header className="workspace-top"><strong><span className="workspace-brand-name">Open Compute System · </span>{t("API 与算力控制台")}</strong><div className="workspace-actions"><PreferencesControls compact/><Badge variant="success">{demoMode?"Mock inference / Mock GPU":t("服务状态在线")}</Badge><Button asChild variant="ghost" size="icon-sm"><Link href="/console/profile" aria-label={t("个人资料")}><CircleUserRound size={20}/></Link></Button></div></header><PublicDemoNotice />{children}</main></div>;
}
