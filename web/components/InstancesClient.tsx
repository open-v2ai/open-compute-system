"use client";

import { Copy, ExternalLink, Plus, Power, PowerOff, RefreshCw, Server, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, formatDate } from "@/lib/api";
import { safeExternalUrl } from "@/lib/security";
import type { Instance, Task } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

const transitional=new Set(["pending","provisioning","starting","stopping","releasing"]);

export function InstancesClient(){
  const{t}=usePreferences();
  const[instances,setInstances]=useState<Instance[]>([]); const[loading,setLoading]=useState(true); const[error,setError]=useState(""); const[actionId,setActionId]=useState("");
  const load=useCallback(async()=>{try{setInstances(await api<Instance[]>("/instances"));setError("")}catch(caught){setError(caught instanceof Error?caught.message:t("加载失败"))}finally{setLoading(false)}},[t]);
  useEffect(()=>{const timeout=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timeout)},[load]);
  const hasTransitional=instances.some((item)=>transitional.has(item.status));
  useEffect(()=>{if(!hasTransitional)return;const timer=window.setInterval(()=>void load(),2000);return()=>window.clearInterval(timer)},[hasTransitional,load]);
  async function action(instance:Instance,type:"start"|"stop"|"release"){
    if(type==="release"){const value=window.prompt(`${t("释放后数据不可恢复。请输入实例名")} ${instance.name} ${t("确认：")}`);if(value!==instance.name)return}
    setActionId(instance.id);setError("");
    try{await api<Task>(`/instances/${instance.id}/${type}`,{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()}});await load()}catch(caught){setError(caught instanceof Error?caught.message:t("操作失败"))}finally{setActionId("")}
  }
  async function copy(value:string){await navigator.clipboard.writeText(value)}
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("容器实例")}</h1><p>{t("实例状态来自持久化任务；创建和生命周期操作会自动轮询。")}</p></div><Button asChild variant="accent"><Link href="/console/create"><Plus/>{t("创建实例")}</Link></Button></div>{error&&<Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}{loading?<Card className="panel">{t("正在加载实例…")}</Card>:instances.length===0?<Card className="panel empty-state"><Server size={36}/><h3>{t("还没有实例")}</h3><p>{t("选择一张有库存的 GPU 开始。")}</p><Button asChild variant="accent"><Link href="/market">{t("去算力市场")}</Link></Button></Card>:instances.map((instance)=>{
    const jupyterUrl=safeExternalUrl(instance.jupyter_url);
    return <Card className="instance-card" key={instance.id}><div className="instance-head"><div><h3>{instance.name}</h3><div className="table-secondary mono">{instance.id} · {formatDate(instance.created_at)}</div></div><StatusPill status={instance.status}/></div><div className="sku-specs"><div><small>GPU</small><strong>{instance.sku.gpu_count} × {instance.sku.gpu_model}</strong></div><div><small>{t("区域")}</small><strong>{instance.sku.region}</strong></div><div><small>{t("vCPU / 内存")}</small><strong>{instance.sku.vcpu} / {instance.sku.memory_gb}GB</strong></div><div><small>{t("镜像")}</small><strong>{instance.image}</strong></div><div><small>{t("计费")}</small><strong>{instance.billing_mode}</strong></div></div>{instance.status==="running"&&instance.ssh_host&&<div className="connection-box"><div className="connection-line"><div><small>SSH</small><div className="mono">ssh root@{instance.ssh_host} -p {instance.ssh_port}</div></div><Button variant="outline" size="sm" onClick={()=>copy(`ssh root@${instance.ssh_host} -p ${instance.ssh_port}`)}><Copy/>{t("复制")}</Button></div><div className="connection-line"><div><small>JupyterLab</small><div>{jupyterUrl??t("地址未通过安全校验")}</div></div>{jupyterUrl&&<Button asChild variant="outline" size="sm"><a href={jupyterUrl} target="_blank" rel="noopener noreferrer"><ExternalLink/>{t("打开")}</a></Button>}</div><p className="form-help">{instance.credential_hint}</p></div>}<div className="instance-actions">{instance.status==="running"&&<Button variant="outline" size="sm" disabled={actionId===instance.id} onClick={()=>action(instance,"stop")}><PowerOff/>{t("关机")}</Button>}{instance.status==="stopped"&&<><Button variant="accent" size="sm" disabled={actionId===instance.id} onClick={()=>action(instance,"start")}><Power/>{t("开机")}</Button><Button variant="destructive" size="sm" disabled={actionId===instance.id} onClick={()=>action(instance,"release")}><Trash2/>{t("释放")}</Button></>}<Button variant="outline" size="sm" onClick={()=>void load()}><RefreshCw/>{t("刷新状态")}</Button></div></Card>
  })}</div>;
}
