"use client";

import { Suspense } from "react";
import { MarketClient } from "@/components/MarketClient";
import { SiteShell } from "@/components/SiteShell";
import { Card } from "@/components/ui/card";
import { usePreferences } from "@/components/PreferencesProvider";

export default function MarketPage() {
  const { t } = usePreferences();
  return <SiteShell><section className="page-hero"><div className="container"><p className="eyebrow">GPU MARKETPLACE</p><h1 className="page-title">{t("选一张合适的卡，")}<br />{t("马上开始。")}</h1><p>{t("按型号、地区、库存和价格筛选。创建前会重新核验库存与余额，相同幂等键不会生成重复实例。")}</p></div></section><section className="section-compact"><div className="container"><Suspense fallback={<Card className="panel">{t("正在加载算力市场…")}</Card>}><MarketClient /></Suspense></div></section></SiteShell>;
}
