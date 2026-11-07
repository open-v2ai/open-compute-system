"use client";

import { SiteShell } from "@/components/SiteShell";
import { usePreferences } from "@/components/PreferencesProvider";
import { Alert, AlertDescription } from "@/components/ui/alert";
export default function PrivacyPage(){const{t}=usePreferences();return <SiteShell><section className="page-hero"><div className="container"><p className="eyebrow">LEGAL · DRAFT</p><h1 className="page-title">{t("隐私政策")}</h1><p>{t("平台仅在注册、交付、客服和安全合规所需范围内处理个人信息。正式版本需补充处理目的、保存期限、第三方清单与用户权利。")}</p></div></section><section className="section"><div className="container" style={{maxWidth:800}}><Alert><AlertDescription>{t("当前为 MVP 占位文本，正式上线前需完成隐私影响评估和法务审核。")}</AlertDescription></Alert></div></section></SiteShell>}
