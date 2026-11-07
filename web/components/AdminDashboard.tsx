"use client";

import { AlertTriangle, ArrowRight, Boxes, CircleDollarSign, Server, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, money } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function AdminDashboard() {
  const { locale, t } = usePreferences();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Dashboard>("/admin/dashboard").then(setData).catch((e) => setError(e.message)); }, []);
  const stats = [
    ["已发布模型", data?.published_models ?? 0, Sparkles],
    ["健康推理副本", data?.healthy_replicas ?? 0, Server],
    ["成功 API 请求", data?.inference_requests ?? 0, Boxes],
    ["Token 收入", money(data?.inference_revenue_cents ?? 0), CircleDollarSign],
  ] as const;
  return <div className="workspace-content">
    <div className="workspace-title"><div><h1>{t("推理商业化看板")}</h1><p>{t("模型、Token、端点和 GPU 实例的数据库实时口径")}</p></div><Badge variant="success">{t("端点状态以健康检查为准")}</Badge></div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    <div className="stat-grid">{stats.map(([label,value,Icon])=><Card className="stat-card" key={label}><div style={{display:"flex",justifyContent:"space-between"}}><small>{t(label)}</small><Icon size={18}/></div><strong>{value}</strong><div className="delta">{t("当前数据库口径")}</div></Card>)}</div>
    <div className="card-grid" style={{marginTop:18}}>
      <Card className="panel" style={{margin:0}}><div className="panel-head"><h2>{t("交付异常")}</h2><AlertTriangle size={18}/></div><strong style={{fontSize:42}}>{data?.failed_tasks??0}</strong><p className="table-secondary">{t("失败或人工复核任务需要处理。")}</p><Link className="card-link" href="/admin/instances">{t("查看任务")} <ArrowRight size={14}/></Link></Card>
      <Card className="panel" style={{margin:0}}><div className="panel-head"><h2>{t("Token 用量")}</h2><Sparkles size={18}/></div><strong style={{fontSize:42}}>{(data?.inference_tokens??0).toLocaleString(locale)}</strong><p className="table-secondary">{t("成功请求的输入与输出 Token 合计。")}</p><Link className="card-link" href="/admin/inference">{t("模型 API 运营")} <ArrowRight size={14}/></Link></Card>
      <Card className="panel" style={{margin:0}}><div className="panel-head"><h2>{t("GPU 实例")}</h2><Server size={18}/></div><strong style={{fontSize:42}}>{data?.running_instances??0}</strong><p className="table-secondary">{t("GPU 实例出租仍作为第二种资源收益模式。")}</p><Link className="card-link" href="/admin/instances">{t("查看实例")} <ArrowRight size={14}/></Link></Card>
    </div>
    <Card className="panel"><Alert><AlertDescription>{t("本地种子模型仍使用 Mock。Token 收入来自平台账本，不代表真实支付到账；生产前必须完成真实端点、限流和用量对账。")}</AlertDescription></Alert></Card>
  </div>;
}
