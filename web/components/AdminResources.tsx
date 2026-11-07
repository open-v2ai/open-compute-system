"use client";

import { ServerCog } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api, formatDate } from "@/lib/api";
import type { Provider } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function AdminResources(){
  const{t}=usePreferences();
  const[items,setItems]=useState<Provider[]>([]); const[error,setError]=useState("");
  useEffect(()=>{api<Provider[]>("/admin/providers").then(setItems).catch((e)=>setError(e.message))},[]);
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("资源来源")}</h1><p>{t("自有资源与固定合作方仅由内部人员维护，不提供供应商登录入口。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Card className="panel"><div className="panel-head"><h2>{t("资源来源列表")}</h2><ServerCog size={20}/></div><div className="table-wrap"><table className="data-table"><thead><tr><th>{t("来源")}</th><th>{t("类型")}</th><th>{t("接入方式")}</th><th>{t("区域")}</th><th>{t("健康")}</th><th>{t("最后更新")}</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td><div className="table-primary">{item.name}</div><div className="table-secondary mono">{item.id}</div></td><td>{t(item.provider_type==="owned"?"自有":"合作方")}</td><td>{item.access_mode}</td><td>{item.region}</td><td><StatusPill status={item.health_status==="healthy"?"active":"failed"}/></td><td>{formatDate(item.updated_at)}</td></tr>)}</tbody></table></div></Card><Card className="panel"><Alert><AlertDescription>{t("PartnerProvider 仅保留接口契约；在未提供正式 API 文档、沙箱账号和幂等能力说明前，不会伪造真实资源同步。")}</AlertDescription></Alert></Card></div>;
}
