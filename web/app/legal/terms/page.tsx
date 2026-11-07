"use client";

import { SiteShell } from "@/components/SiteShell";
import { usePreferences } from "@/components/PreferencesProvider";
import { Alert, AlertDescription } from "@/components/ui/alert";
export default function TermsPage(){const{t}=usePreferences();return <SiteShell><section className="page-hero"><div className="container"><p className="eyebrow">LEGAL · DRAFT</p><h1 className="page-title">{t("服务协议")}</h1><p>{t("当前为 MVP 占位版本，正式上线前须由业务主体和法务审核、定版并记录协议版本。")}</p></div></section><section className="section"><div className="container" style={{maxWidth:800}}><Alert><AlertDescription>{t("本页面不构成正式法律文本。请勿在未完成主体、支付、计费、退款和数据处理条款审核前对外商用。")}</AlertDescription></Alert></div></section></SiteShell>}
