"use client";

import { ReceiptText } from "lucide-react";
import { useEffect,useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api,formatDate,money } from "@/lib/api";
import type { AdminOrder } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function AdminOrders(){
  const{t}=usePreferences();
  const[orders,setOrders]=useState<AdminOrder[]>([]); const[error,setError]=useState("");
  useEffect(()=>{api<AdminOrder[]>("/admin/orders").then(setOrders).catch((e)=>setError(e.message))},[]);
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("订单与财务")}</h1><p>{t("订单按交付状态流转；演示扣款和失败退款均有流水。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Card className="panel"><div className="panel-head"><h2>{t("订单列表")}</h2><ReceiptText size={20}/></div><div className="table-wrap"><table className="data-table"><thead><tr><th>{t("订单号")}</th><th>{t("用户")}</th><th>{t("商品")}</th><th>{t("计费")}</th><th>{t("金额")}</th><th>{t("状态")}</th><th>{t("创建时间")}</th></tr></thead><tbody>{orders.map(order=><tr key={order.id}><td className="mono">{order.id}</td><td>{order.user}<div className="table-secondary mono">{order.user_id}</div><div className="table-secondary">{order.contact}</div></td><td>{order.sku}</td><td>{order.billing_mode}</td><td>{money(order.amount_cents)}</td><td><StatusPill status={order.status}/></td><td>{formatDate(order.created_at)}</td></tr>)}</tbody></table></div></Card><Card className="panel"><Alert><AlertDescription>{t("在线支付、精确计费和真实退款仍属于外部渠道能力；当前资金流水只验证平台内部一致性。")}</AlertDescription></Alert></Card></div>;
}
