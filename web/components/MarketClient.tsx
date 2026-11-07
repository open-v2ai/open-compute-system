"use client";

import { Bell, Boxes, Filter, MapPin, RefreshCw, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api, money } from "@/lib/api";
import type { SKU } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function MarketClient() {
  const { t } = usePreferences();
  const search = useSearchParams();
  const router = useRouter();
  const [skus, setSkus] = useState<SKU[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const gpu = search.get("gpu") ?? "";
  const region = search.get("region") ?? "";
  const sort = search.get("sort") ?? "recommended";
  const inStock = search.get("stock") === "1";

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const params = new URLSearchParams();
    if (gpu) params.set("gpu_model", gpu);
    if (region) params.set("region", region);
    if (inStock) params.set("in_stock", "true");
    params.set("sort", sort);
    try { setSkus(await api<SKU[]>(`/market/skus?${params}`)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : t("加载失败")); }
    finally { setLoading(false); }
  }, [gpu, region, sort, inStock, t]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  function update(key: string, value: string) {
    const params = new URLSearchParams(search.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.replace(`/market?${params.toString()}`, { scroll: false });
  }

  const gpuOptions = useMemo(() => ["", "RTX 4090", "A100", "H20", "L40S"], []);
  const regionOptions = ["", "华东·上海", "华东·杭州", "华北·北京", "华南·深圳"];

  return <div className="market-layout">
    <aside className="filters" aria-label={t("商品筛选")}>
      <div className="filter-group"><label htmlFor="gpu"><Filter size={13} style={{display:"inline",marginRight:5}} />{t("GPU 型号")}</label><NativeSelect id="gpu" value={gpu} onChange={e => update("gpu", e.target.value)}>{gpuOptions.map(item => <option value={item} key={item || "all"}>{item || t("全部型号")}</option>)}</NativeSelect></div>
      <div className="filter-group"><label htmlFor="region"><MapPin size={13} style={{display:"inline",marginRight:5}} />{t("区域")}</label><NativeSelect id="region" value={region} onChange={e => update("region", e.target.value)}>{regionOptions.map(item => <option value={item} key={item || "all"}>{item ? t(item) : t("全部区域")}</option>)}</NativeSelect></div>
      <div className="filter-group"><label htmlFor="sort"><SlidersHorizontal size={13} style={{display:"inline",marginRight:5}} />{t("排序")}</label><NativeSelect id="sort" value={sort} onChange={e => update("sort", e.target.value)}><option value="recommended">{t("综合推荐")}</option><option value="price_asc">{t("价格从低到高")}</option><option value="price_desc">{t("价格从高到低")}</option></NativeSelect></div>
      <Label className="check-row"><Checkbox checked={inStock} onCheckedChange={checked => update("stock", checked === true ? "1" : "")} />{t("只看有货")}</Label>
    </aside>
    <div>
      <div className="market-toolbar"><div><strong>{loading ? t("正在刷新库存…") : `${skus.length}${t("个可选规格")}`}</strong><div className="table-secondary">{t("库存与价格在创建前会再次校验")}</div></div><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw />{t("刷新")}</Button></div>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {!loading && !error && skus.length === 0 && <Card className="panel empty-state"><Boxes size={34} /><h3>{t("没有匹配的算力")}</h3><p>{t("可以清空筛选，或提交到货与资源需求。")}</p><Button variant="outline" onClick={() => router.replace("/market")}>{t("清空筛选")}</Button></Card>}
      <div className="sku-list">{skus.map(sku => <Card className="sku-card" key={sku.id}>
        <div className="sku-top"><div className="sku-title"><span className="gpu-badge">{sku.gpu_model}</span><div><div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>{sku.tag && <Badge variant="success">{sku.tag}</Badge>}<Badge variant={sku.inventory_available > 0 ? "success" : "secondary"}>{sku.inventory_available > 0 ? `${sku.inventory_available} ${t("可售")}` : t("暂时无货")}</Badge></div><h3>{sku.name}</h3><span className="table-secondary">{sku.region} · {sku.zone}</span></div></div></div>
        <div className="sku-specs"><div><small>GPU</small><strong>{sku.gpu_count} × {sku.gpu_model} {sku.gpu_memory_gb}G</strong></div><div><small>vCPU</small><strong>{sku.vcpu}{t("核")}</strong></div><div><small>{t("内存")}</small><strong>{sku.memory_gb} GB</strong></div><div><small>{t("系统盘")}</small><strong>{sku.system_disk_gb} GB</strong></div><div><small>{t("数据盘")}</small><strong>{sku.data_disk_gb} GB</strong></div></div>
        <div className="sku-bottom"><div className="price"><strong>{money(sku.price_hour_cents)}</strong><span> / {t("小时")}</span><div className="table-secondary">{t("包月")} {money(sku.price_month_cents)}</div></div>{sku.inventory_available > 0 ? <Button asChild variant="accent"><Link href={`/console/create?sku=${sku.id}`}>{t("立即创建")}</Link></Button> : <Button asChild variant="outline"><Link href="/about#contact"><Bell />{t("到货提醒")}</Link></Button>}</div>
      </Card>)}</div>
    </div>
  </div>;
}
