"use client";

import { ReceiptText } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api, formatDate, money } from "@/lib/api";
import type { Order, WalletTransaction } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function OrdersClient(){
  const {t}=usePreferences();
  const[orders,setOrders]=useState<Order[]>([]); const[transactions,setTransactions]=useState<WalletTransaction[]>([]); const[error,setError]=useState("");
  useEffect(()=>{Promise.all([api<Order[]>("/orders"),api<WalletTransaction[]>("/wallet/transactions")]).then(([o,t])=>{setOrders(o);setTransactions(t)}).catch((e)=>setError(e.message))},[]);
  return <div className="workspace-content"><div className="workspace-title"><div><h1>{t("我的订单")}</h1><p>{t("订单、演示扣款和失败退款保持同一业务口径。")}</p></div></div>{error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}<Card className="panel">{orders.length===0?<div className="empty-state"><ReceiptText size={34}/><h3>{t("暂无订单")}</h3></div>:<div className="table-wrap"><table className="data-table"><thead><tr><th>{t("订单号")}</th><th>{t("商品")}</th><th>{t("计费方式")}</th><th>{t("金额")}</th><th>{t("状态")}</th><th>{t("创建时间")}</th></tr></thead><tbody>{orders.map(order=><tr key={order.id}><td className="mono">{order.id}</td><td className="table-primary">{order.sku.name}</td><td>{order.billing_mode}</td><td>{money(order.amount_cents)}</td><td><StatusPill status={order.status}/></td><td>{formatDate(order.created_at)}</td></tr>)}</tbody></table></div>}</Card><Card className="panel"><div className="panel-head"><h2>{t("演示资金流水")}</h2></div><div className="table-wrap"><table className="data-table"><thead><tr><th>{t("时间")}</th><th>{t("类型")}</th><th>{t("变动")}</th><th>{t("变动后余额")}</th><th>{t("说明")}</th></tr></thead><tbody>{transactions.map((row)=><tr key={row.id}><td>{formatDate(row.created_at)}</td><td>{row.transaction_type}</td><td>{money(row.amount_cents)}</td><td>{money(row.balance_after_cents)}</td><td>{row.description}</td></tr>)}</tbody></table></div></Card><Card className="panel"><Alert><AlertDescription>{t("在线支付、精确计费、真实退款和发票渠道仍未接入。")}</AlertDescription></Alert></Card></div>;
}
