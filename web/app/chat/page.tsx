"use client";

import { Suspense } from "react";
import { ChatClient } from "@/components/ChatClient";
import { SiteShell } from "@/components/SiteShell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { usePreferences } from "@/components/PreferencesProvider";

export default function ChatPage() {
  const { t } = usePreferences();
  return (
    <SiteShell>
      <section className="section-compact" style={{ paddingTop: 24, paddingBottom: 40 }}>
        <div className="container">
          <Alert className="mb-5"><AlertDescription>
            {t("网页 Chat 使用与 API Key 相同的模型网关和 Token 计量。演示环境模型由 Mock 生成；生产结果取决于运营方实际接入的推理端点。")}
          </AlertDescription></Alert>
          <Suspense fallback={<Card className="panel">{t("正在加载 Chat…")}</Card>}>
            <ChatClient />
          </Suspense>
        </div>
      </section>
    </SiteShell>
  );
}
