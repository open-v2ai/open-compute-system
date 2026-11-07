"use client";

import { SiteShell } from "@/components/SiteShell";
import { usePreferences } from "@/components/PreferencesProvider";
import { Alert, AlertDescription } from "@/components/ui/alert";
export default function AntiMiningPage(){const{t}=usePreferences();return <SiteShell><section className="page-hero"><div className="container"><p className="eyebrow">ACCEPTABLE USE</p><h1 className="page-title">{t("反挖矿与可接受使用")}</h1><p>{t("禁止将平台资源用于数字货币挖矿、攻击、恶意程序传播、绕过监管或其他违法违规活动。风险行为可触发限制、关机、隔离与人工复核。")}</p></div></section><section className="section"><div className="container" style={{maxWidth:800}}><Alert><AlertDescription>{t("自动强制关机必须保留证据摘要并通知用户；正式规则和申诉机制需在上线前由运营与法务确认。")}</AlertDescription></Alert></div></section></SiteShell>}
