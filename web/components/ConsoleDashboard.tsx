"use client";

import { ArrowRight, Cpu, KeyRound, Plus, Server, Waypoints } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isPublicDemo } from "@/lib/deployment";
import { api, money } from "@/lib/api";
import type { ApiKey, Instance, UsageEvent, User } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

const demoMode = process.env.NODE_ENV !== "production" || isPublicDemo();

export function ConsoleDashboard() {
  const { locale, t } = usePreferences();
  const [user, setUser] = useState<User | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<UsageEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<User>("/auth/me"),
      api<Instance[]>("/instances"),
      api<ApiKey[]>("/inference/keys"),
      api<UsageEvent[]>("/inference/usage"),
    ])
      .then(([userRow, instanceRows, keyRows, usageRows]) => {
        setUser(userRow);
        setInstances(instanceRows);
        setKeys(keyRows);
        setUsage(usageRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const running = instances.filter((item) => item.status === "running").length;
  const activeKeys = keys.filter((key) => key.status === "active").length;
  const totalTokens = usage.reduce(
    (sum, row) => sum + row.prompt_tokens + row.completion_tokens,
    0,
  );

  return (
    <div className="workspace-content">
      <div className="workspace-title">
        <div>
          <h1>{t("你好")}，{user?.nickname ?? t("API 用户")}</h1>
          <p>{t("从这里管理模型 API Key、Token 用量和 GPU 实例。")}</p>
        </div>
        <Button asChild variant="accent"><Link href="/console/keys"><KeyRound /> {t("创建 API Key")}</Link></Button>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <div className="stat-grid">
        <Card className="stat-card"><small>{t("可用额度")}</small><strong>{money(user?.balance_cents ?? 0)}</strong><div className="delta">{t(demoMode ? "演示额度，不是真实充值" : "实例与 Token 共用账户")}</div></Card>
        <Card className="stat-card"><small>{t("有效 API Keys")}</small><strong>{activeKeys}</strong><div className="delta">{locale === "zh-CN" ? `共 ${keys.length} 个 Key` : `${keys.length}${t("个 Key")}`}</div></Card>
        <Card className="stat-card"><small>{t("累计 Tokens")}</small><strong>{totalTokens.toLocaleString(locale)}</strong><div className="delta">{t("输入与输出合计")}</div></Card>
        <Card className="stat-card"><small>{t("运行实例")}</small><strong>{running}</strong><div className="delta">{locale === "zh-CN" ? `共 ${instances.length} 个实例` : `${instances.length}${t("个实例")}`}</div></Card>
      </div>

      <Card className="panel">
        <div className="panel-head">
          <h2>{t("模型 API 快速入口")}</h2>
          <Link className="card-link" href="/models">{t("查看模型")} <ArrowRight size={15} /></Link>
        </div>
        <div className="card-grid">
          <div><Waypoints size={20} /><h3>{t("统一 base URL")}</h3><p className="table-secondary">{t("兼容 OpenAI Chat Completions，模型和副本由运营方统一发布。")}</p></div>
          <div><KeyRound size={20} /><h3>{t("Key 策略")}</h3><p className="table-secondary">{t("配置 RPM、TPM、额度和允许模型；吊销后下一次请求即失效。")}</p></div>
          <div><Cpu size={20} /><h3>{t("Token 计量")}</h3><p className="table-secondary">{t("输入、输出 Token、延迟、副本和扣费均可追踪。")}</p></div>
        </div>
      </Card>

      <Card className="panel">
        <div className="panel-head">
          <h2>{t("最近实例")}</h2>
          <Link className="card-link" href="/console/instances">{t("查看全部")} <ArrowRight size={15} /></Link>
        </div>
        {instances.length === 0 ? (
          <div className="empty-state">
            <Server size={34} />
            <h3>{t("还没有 GPU 实例")}</h3>
            <p>{t("如需原始算力，可以从 GPU 市场创建实例。")}</p>
            <Button asChild variant="outline"><Link href="/market"><Plus /> {t("GPU 市场")}</Link></Button>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>{t("实例")}</th><th>{t("配置")}</th><th>{t("区域")}</th><th>{t("状态")}</th><th>{t("创建时间")}</th></tr></thead>
              <tbody>
                {instances.slice(0, 5).map((instance) => (
                  <tr key={instance.id}>
                    <td><div className="table-primary">{instance.name}</div><div className="table-secondary mono">{instance.id}</div></td>
                    <td>{instance.sku.gpu_count} × {instance.sku.gpu_model}</td>
                    <td>{instance.sku.region}</td>
                    <td><StatusPill status={instance.status} /></td>
                    <td>{new Date(instance.created_at).toLocaleString(locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="panel">
        <div className="panel-head"><h2>{t("当前验收边界")}</h2></div>
        <Alert><AlertDescription>
          {demoMode
            ? t("本地模型与 GPU 资源均为 Mock。真实推理端点、生产限流和真实 GPU 交付需要独立验收。")
            : t("只调用运营方已发布并通过健康检查的模型；外部运行时状态仍需持续监控。")}
        </AlertDescription></Alert>
      </Card>
    </div>
  );
}
