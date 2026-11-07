"use client";

import { Suspense } from "react";
import { ModelsCatalogClient } from "@/components/ModelsCatalogClient";
import { SiteShell } from "@/components/SiteShell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { usePreferences } from "@/components/PreferencesProvider";

export default function ModelsPage() {
  const { t } = usePreferences();
  return (
    <SiteShell>
      <section className="page-hero">
        <div className="container">
          <p className="eyebrow">OPENAI-COMPATIBLE MODEL API</p>
          <h1 className="page-title">
            {t("一个模型目录，")}
            <br />
            {t("一套可计费 API。")}
          </h1>
          <p>
            {t("用户通过统一 base URL 和 API Key 调用资源方发布的模型。输入、输出 Token 分别计量，每个 Key 可配置额度、RPM、TPM 和模型范围。")}
          </p>
          <Alert className="mt-5"><AlertDescription>{t("本地演示模型仍由 Mock 生成；只有运营后台接入并通过健康检查的真实端点才能作为生产模型上架。")}</AlertDescription></Alert>
        </div>
      </section>
      <section className="section-compact">
        <div className="container">
          <Suspense fallback={<Card className="panel">{t("正在加载模型…")}</Card>}>
            <ModelsCatalogClient />
          </Suspense>
        </div>
      </section>
    </SiteShell>
  );
}
