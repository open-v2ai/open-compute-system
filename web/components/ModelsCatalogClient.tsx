"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Gauge,
  MessageSquareText,
  Route,
  Sparkles,
  Zap,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { api, money } from "@/lib/api";
import type { InferenceModel } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function ModelsCatalogClient() {
  const { t } = usePreferences();
  const [models, setModels] = useState<InferenceModel[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      api<InferenceModel[]>("/inference/models")
        .then(setModels)
        .catch((err) => setError(err.message));
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);

  const autoRouter = models.find((model) => model.is_auto_router);
  const directModels = models.filter((model) => !model.is_auto_router);

  return (
    <div>
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}

      {autoRouter && (
        <Card className="auto-router-spotlight">
          <div className="auto-router-grid" aria-hidden="true" />
          <CardContent className="auto-router-content">
            <div className="auto-router-copy">
              <Badge className="auto-router-badge">
                <Sparkles /> {t("核心推荐")}
              </Badge>
              <p className="auto-router-overline">OPENCOMPUTE INTELLIGENT ROUTING</p>
              <h2>
                {t("一个模型入口，")}
                <span>{t("自动匹配合适能力。")}</span>
              </h2>
              <p className="auto-router-lead">
                {t("无需在业务代码里维护模型判断逻辑。简单问题交给轻量模型，复杂任务自动切换到更强模型。")}
              </p>
              <div className="auto-router-benefits" aria-label={t("Auto Router 核心优势")}>
                <span><CheckCircle2 />{t("一个稳定模型 ID")}</span>
                <span><Gauge />{t("兼顾响应成本与质量")}</span>
              </div>
              <div className="auto-router-actions">
                <Button asChild variant="accent" size="lg">
                  <Link href={`/chat?model=${encodeURIComponent(autoRouter.slug)}`}>
                    {t("立即使用 Auto Router")} <ArrowRight />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="auto-router-key-button">
                  <Link href="/console/keys">{t("创建 API Key")}</Link>
                </Button>
              </div>
              <div className="auto-router-meta">
                <span className="mono">{autoRouter.slug}</span>
                <span>
                  {t("上下文")} {autoRouter.context_length.toLocaleString()}
                </span>
                <span>
                  Prompt {money(autoRouter.price_prompt_per_mtok_cents)}/MTok · Completion{" "}
                  {money(autoRouter.price_completion_per_mtok_cents)}/MTok
                </span>
              </div>
            </div>

            <div className="auto-router-visual" aria-label={t("Auto Router 路由流程")}>
              <div className="auto-router-visual-head">
                <span>{t("实时判断请求复杂度")}</span>
                <Route aria-hidden="true" />
              </div>
              <div className="auto-router-flow">
                <div className="auto-router-node auto-router-request">
                  <MessageSquareText aria-hidden="true" />
                  <div><small>{t("用户请求")}</small><strong>Prompt</strong></div>
                </div>
                <ArrowRight className="auto-router-arrow" aria-hidden="true" />
                <div className="auto-router-node auto-router-hub">
                  <Sparkles aria-hidden="true" />
                  <div><small>{t("复杂度判断")}</small><strong>Auto Router</strong></div>
                </div>
                <ArrowRight className="auto-router-arrow" aria-hidden="true" />
                <div className="auto-router-branches">
                  <div><Zap aria-hidden="true" /><span><small>{t("简单问题")}</small><strong>{t("轻量模型")}</strong></span></div>
                  <div><BrainCircuit aria-hidden="true" /><span><small>{t("复杂任务")}</small><strong>{t("强模型")}</strong></span></div>
                </div>
              </div>
              <p>{t("应用侧只需要调用 Auto，路由策略由平台统一配置并即时生效。")}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {directModels.length > 0 && (
        <section className="direct-models-section">
          <div className="direct-models-head">
            <div>
              <p className="eyebrow">DIRECT MODEL ACCESS</p>
              <h2>{t("手动选择模型")}</h2>
            </div>
            <p>{t("如果你已经明确能力和成本要求，也可以直接调用指定模型。")}</p>
          </div>
          <div className="card-grid">
            {directModels.map((model) => (
          <Card className="card" key={model.id}>
            <CardHeader className="p-0"><p className="eyebrow">OPENAI-COMPATIBLE API</p><CardTitle>{model.display_name}</CardTitle><p className="table-secondary mono">{model.slug}</p></CardHeader>
            <CardContent className="p-0"><p>{model.description}</p><p className="table-secondary">
              {t("上下文")} {model.context_length.toLocaleString()} · Prompt{" "}
              {money(model.price_prompt_per_mtok_cents)}/MTok · Completion{" "}
              {money(model.price_completion_per_mtok_cents)}/MTok
            </p></CardContent>
            <CardFooter className="gap-2 p-0 pt-4"><Button asChild variant="accent" size="sm"><Link href={`/chat?model=${encodeURIComponent(model.slug)}`}>{t("网页 Chat")}</Link></Button><Button asChild variant="outline" size="sm"><Link href="/console/keys">{t("创建 API Key")}</Link></Button></CardFooter>
          </Card>
            ))}
          </div>
        </section>
      )}
      {models.length === 0 && !error && <div className="panel">{t("正在加载模型目录…")}</div>}
    </div>
  );
}
