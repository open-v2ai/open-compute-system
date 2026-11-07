"use client";

import { ArrowRight, Boxes, Cable, CheckCircle2, Gauge, ServerCog, TimerReset, Workflow } from "lucide-react";
import Link from "next/link";
import { SiteShell } from "@/components/SiteShell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePreferences } from "@/components/PreferencesProvider";

const loopCards = [
  {
    icon: <Boxes />,
    title: "接入模型端点",
    copy: "登记 vLLM、NIM 或其他 OpenAI-compatible 端点，内部地址与凭据不暴露给 API 用户。",
  },
  {
    icon: <Workflow />,
    title: "发布模型 API",
    copy: "设置公开模型 ID、输入/输出 Token 售价、容量和健康副本，再发布统一 API。",
  },
  {
    icon: <Cable />,
    title: "发 Key 并计费",
    copy: "API Key、RPM、TPM、模型权限、Token 用量和余额扣减走同一套商业化网关。",
  },
];

export default function Home() {
  const { t } = usePreferences();
  return (
    <SiteShell>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <p className="eyebrow">AI INFERENCE COMMERCE INFRASTRUCTURE</p>
            <h1>
              {t("把自有 GPU，")}
              <span>{t("发布成可计费的模型 API。")}</span>
            </h1>
            <p className="hero-copy">
              {t("Open Compute System 是部署在资源方环境中的平台软件。统一管理 GPU、模型端点、OpenAI 兼容 API、API Key、Token 计量计费和 GPU 实例交付。")}
            </p>
            <div className="hero-actions">
              <Button asChild variant="accent"><Link href="/models">{t("查看模型 API")} <ArrowRight /></Link></Button>
              <Button asChild variant="outline"><Link href="/console/keys">{t("创建 API Key")}</Link></Button>
            </div>
            <div className="trust-row">
              <span>
                <CheckCircle2 size={15} />{t("OpenAI 兼容接口")}
              </span>
              <span>
                <CheckCircle2 size={15} />{t("输入/输出 Token 计量")}
              </span>
              <span>
                <CheckCircle2 size={15} />{t("运行时 Adapter 可替换")}
              </span>
            </div>
          </div>
          <div className="gpu-visual" aria-label={t("控制面状态示意")}>
            <div className="gpu-meta mono">
              <span>INFERENCE CONTROL PLANE</span>
              <span>GATEWAY · READY</span>
            </div>
            <div className="gpu-chip">
              <span className="gpu-name mono">GPU → MODEL → API → TOKEN</span>
            </div>
            <div className="metric-strip">
              <div>
                <strong>API Key</strong>
                <small>{t("哈希存储")}</small>
              </div>
              <div>
                <strong>Metered</strong>
                <small>{t("Token 幂等结算")}</small>
              </div>
              <div>
                <strong>Adapter</strong>
                <small>{t("接入真实端点")}</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-head">
            <div>
              <p className="eyebrow">TOKEN COMMERCE LOOP</p>
              <h2>
                {t("一套平台，")}
                <br />
                {t("从 GPU 到收费 API。")}
              </h2>
            </div>
            <p>{t("资源方保留自己的硬件、模型、客户、价格和经营数据；平台只提供底层软件与运营控制面。")}</p>
          </div>
          <div className="card-grid">
            {loopCards.map((card) => (
              <Card className="card" key={card.title}>
                <CardHeader className="p-0">
                  <div className="card-icon">{card.icon}</div>
                  <CardTitle>{t(card.title)}</CardTitle>
                </CardHeader>
                <CardContent className="p-0"><p>{t(card.copy)}</p></CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="dark-section section">
        <div className="container">
          <div className="section-head">
            <div>
              <p className="eyebrow">BRING YOUR OWN GPU & RUNTIME</p>
              <h2>
                {t("演示用 Mock，")}
                <br />
                {t("生产接真实端点。")}
              </h2>
            </div>
            <p>
              {t("P1 可登记已有 vLLM/NIM/OpenAI-compatible 端点；远程 GPU 上自动拉起模型容器由后续节点 Agent 负责。")}
            </p>
          </div>
          <div className="card-grid">
            <Card className="card">
              <TimerReset />
              <CardTitle>MockInference</CardTitle>
              <CardContent className="p-0"><p>{t("本地和测试保留可重复演示，但生产默认禁止发布 Mock 模型。")}</p></CardContent>
            </Card>
            <Card className="card">
              <ServerCog />
              <CardTitle>OpenAI-compatible Adapter</CardTitle>
              <CardContent className="p-0"><p>
                {t("连接 vLLM、NIM 或兼容端点；统一鉴权、错误映射、Token 用量和副本健康。")}
              </p></CardContent>
            </Card>
            <Card className="card">
              <Gauge />
              <CardTitle>{t("模型运营控制面")}</CardTitle>
              <CardContent className="p-0"><p>{t("配置模型、副本、成本、售价、容量和发布状态，查看 Token 用量与经营结果。")}</p></CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section className="section-compact">
        <div className="container">
          <Alert className="mb-7"><AlertDescription>{t("当前仓库已具备真实端点接入代码，但本地演示数据仍是 Mock。未完成真实端点与生产限流验收前，不得宣称模型 API 已投入生产。")}</AlertDescription></Alert>
          <div className="gpu-visual" style={{ minHeight: 0, padding: 42 }}>
            <div className="section-head" style={{ position: "relative", zIndex: 2, margin: 0 }}>
              <div>
                <p className="eyebrow">TRY THE API LOOP</p>
                <h2 style={{ fontSize: "clamp(34px,5vw,60px)" }}>
                  {t("选择一个模型，")}
                  <br />
                  {t("创建 Key 并调用 API。")}
                </h2>
              </div>
              <Button asChild variant="accent"><Link href="/models">{t("进入模型目录")} <ArrowRight /></Link></Button>
            </div>
          </div>
        </div>
      </section>
    </SiteShell>
  );
}
