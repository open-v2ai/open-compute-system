"use client";

import { ArrowLeft, CheckCircle2, Cpu, HardDrive, ImageIcon, MapPin } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, money } from "@/lib/api";
import type { SKU } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

const images=["PyTorch 2.7 · CUDA 12.8","ComfyUI · CUDA 12.6","Qwen / vLLM 推理环境","Ubuntu 22.04 · CUDA 12.4"];
const modes=[{id:"hourly",label:"按量",key:"price_hour_cents",unit:"小时"},{id:"daily",label:"包日",key:"price_day_cents",unit:"天"},{id:"weekly",label:"包周",key:"price_week_cents",unit:"周"},{id:"monthly",label:"包月",key:"price_month_cents",unit:"月"}] as const;

export function CreateInstanceClient(){
  const{t}=usePreferences();
  const search=useSearchParams();const router=useRouter();const[skus,setSkus]=useState<SKU[]>([]);const[skuId,setSkuId]=useState(search.get("sku")??"");const[mode,setMode]=useState<(typeof modes)[number]["id"]>("hourly");const[busy,setBusy]=useState(false);const[error,setError]=useState("");
  useEffect(()=>{api<SKU[]>("/market/skus?sort=recommended").then(items=>{setSkus(items);setSkuId(current=>current||items.find(item=>item.inventory_available>0)?.id||"");});},[]);
  const sku=useMemo(()=>skus.find(item=>item.id===skuId),[skus,skuId]);
  const price=sku?sku[modes.find(item=>item.id===mode)!.key]:0;
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!sku)return;setBusy(true);setError("");const data=new FormData(event.currentTarget);try{const result=await api<{instance_id:string;task_id:string}>("/instances",{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({sku_id:sku.id,name:data.get("name"),image:data.get("image"),billing_mode:mode})});router.push(`/console/instances?task=${result.task_id}`);}catch(caught){setError(caught instanceof Error?caught.message:t("创建失败"));setBusy(false);}}
  return <div className="workspace-content"><div className="workspace-title"><div><Link className="card-link" href="/market"><ArrowLeft size={15}/>{t("返回市场")}</Link><h1 style={{marginTop:14}}>{t("创建 GPU 实例")}</h1><p>{t("确认算力、镜像与计费方式，提交后立即返回任务 ID。")}</p></div></div>{!sku?<Card className="panel">{t("正在加载可用算力…")}</Card>:<form onSubmit={submit}><Card className="panel"><div className="panel-head"><h2>{t("1. 选择算力")}</h2><span className="stock">● {sku.inventory_available}{t("个可售")}</span></div><NativeSelect value={skuId} onChange={e=>setSkuId(e.target.value)}>{skus.map(item=><option key={item.id} value={item.id} disabled={item.inventory_available===0}>{item.name} · {item.region} {item.inventory_available===0?`(${t("无货")})`:""}</option>)}</NativeSelect><div className="sku-specs"><div><small>GPU</small><strong>{sku.gpu_count} × {sku.gpu_model} {sku.gpu_memory_gb}G</strong></div><div><small>vCPU</small><strong>{sku.vcpu}{t("核")}</strong></div><div><small>{t("内存")}</small><strong>{sku.memory_gb} GB</strong></div><div><small>{t("系统盘")}</small><strong>{sku.system_disk_gb} GB</strong></div><div><small>{t("数据盘")}</small><strong>{sku.data_disk_gb} GB</strong></div></div></Card><Card className="panel"><div className="panel-head"><h2>{t("2. 开发环境")}</h2><ImageIcon size={20}/></div><div className="form-grid"><div className="form-row"><Label htmlFor="image">{t("镜像")}</Label><NativeSelect id="image" name="image">{images.map(image=><option key={image}>{t(image)}</option>)}</NativeSelect></div><div className="form-row"><Label htmlFor="name">{t("实例名称")}</Label><Input id="name" name="name" defaultValue={`train-${sku.gpu_model.toLowerCase().replace(" ","")}`} required minLength={2}/></div></div></Card><Card className="panel"><div className="panel-head"><h2>{t("3. 计费方式")}</h2><span className="table-secondary">{t("演示额度，不发生真实扣款")}</span></div><RadioGroup name="mode" value={mode} onValueChange={value=>setMode(value as (typeof modes)[number]["id"])} className="card-grid">{modes.map(item=><Label className="card" style={{padding:18,cursor:"pointer",borderColor:mode===item.id?"var(--blue)":undefined}} key={item.id} htmlFor={`mode-${item.id}`}><RadioGroupItem id={`mode-${item.id}`} value={item.id}/><strong style={{display:"block",margin:"10px 0 4px"}}>{t(item.label)}</strong><span>{money(sku[item.key])} / {t(item.unit)}</span></Label>)}</RadioGroup></Card><Card className="panel"><div className="panel-head"><h2>{t("订单确认")}</h2><CheckCircle2 size={20}/></div><div className="form-grid"><div><div className="connection-line"><span><Cpu size={15}/> {t("配置")}</span><strong>{sku.gpu_count} × {sku.gpu_model}</strong></div><div className="connection-line"><span><MapPin size={15}/> {t("区域")}</span><strong>{sku.region}</strong></div><div className="connection-line"><span><HardDrive size={15}/> {t("磁盘")}</span><strong>{sku.system_disk_gb + sku.data_disk_gb} GB</strong></div></div><div><div className="price"><span>{t("本周期预计扣款")}</span><br/><strong>{money(price)}</strong></div><p className="form-help">{t("释放会永久删除演示系统盘与数据盘。真实支付与精确计费不在本期能力内。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Button variant="accent" style={{marginTop:22}} disabled={busy||sku.inventory_available===0}>{t(busy?"正在提交…":"确认并创建实例")}</Button></Card></form>}</div>;
}
