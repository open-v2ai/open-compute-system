"use client";

import { FileClock } from "lucide-react";
import { useEffect,useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api,formatDate } from "@/lib/api";
import type { Audit } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function AdminAudit(){
  const{t}=usePreferences();
  const[rows,setRows]=useState<Audit[]>([]); const[error,setError]=useState("");
  useEffect(()=>{api<Audit[]>("/admin/audit-logs").then(setRows).catch((e)=>setError(e.message))},[]);
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("审计日志")}</h1><p>{t("登录、商品、资金和任务写操作均关联请求 ID。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Card className="panel"><div className="panel-head"><h2>{t("最近 200 条")}</h2><FileClock size={20}/></div><div className="table-wrap"><table className="data-table"><thead><tr><th>{t("时间")}</th><th>{t("操作者")}</th><th>{t("动作")}</th><th>{t("对象")}</th><th>{t("请求 ID")}</th><th>{t("结果")}</th><th>{t("摘要")}</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td>{formatDate(row.created_at)}</td><td>{row.actor_type}<div className="table-secondary mono">{row.actor_id}</div></td><td className="mono">{row.action}</td><td>{row.object_type}<div className="table-secondary mono">{row.object_id}</div></td><td className="mono">{row.request_id??"—"}</td><td>{row.result}</td><td><code style={{fontSize:11}}>{row.summary?JSON.stringify(row.summary):"—"}</code></td></tr>)}</tbody></table></div></Card></div>;
}
