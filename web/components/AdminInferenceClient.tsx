"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, ServerCog } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api, money } from "@/lib/api";
import type {
  AdminInferenceModel,
  AdminInferenceReplica,
  UsageEvent,
} from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { AdminInferenceInfrastructure } from "./AdminInferenceInfrastructure";
import { usePreferences } from "./PreferencesProvider";

export function AdminInferenceClient() {
  const { t } = usePreferences();
  const [models, setModels] = useState<AdminInferenceModel[]>([]);
  const [replicas, setReplicas] = useState<AdminInferenceReplica[]>([]);
  const [usage, setUsage] = useState<UsageEvent[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [showModelForm, setShowModelForm] = useState(false);
  const [showReplicaForm, setShowReplicaForm] = useState(false);
  const [error, setError] = useState("");

  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? null,
    [models, selectedModelId],
  );
  const directModels = useMemo(
    () => models.filter((model) => !model.is_auto_router && model.status === "published"),
    [models],
  );

  const loadReplicas = useCallback(async (modelId: string) => {
    if (!modelId) {
      setReplicas([]);
      return;
    }
    setReplicas(
      await api<AdminInferenceReplica[]>(
        "/admin/inference/models/" + modelId + "/replicas",
      ),
    );
  }, []);

  const load = useCallback(async () => {
    const [modelRows, usageRows] = await Promise.all([
      api<AdminInferenceModel[]>("/admin/inference/models"),
      api<UsageEvent[]>("/admin/inference/usage"),
    ]);
    setModels(modelRows);
    setUsage(usageRows);
    const nextId =
      selectedModelId && modelRows.some((row) => row.id === selectedModelId)
        ? selectedModelId
        : (modelRows[0]?.id ?? "");
    setSelectedModelId(nextId);
    await loadReplicas(nextId);
  }, [loadReplicas, selectedModelId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void load().catch((err: Error) => setError(err.message));
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  async function toggle(model: AdminInferenceModel) {
    setError("");
    try {
      await api("/admin/inference/models/" + model.id, {
        method: "PATCH",
        body: JSON.stringify({
          version: model.version,
          status: model.status === "published" ? "unpublished" : "published",
          reason: "运营上下架",
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("更新失败"));
    }
  }

  async function editPrice(model: AdminInferenceModel) {
    const promptPrice = window.prompt(
      t("输入单价（元 / MTok）"),
      String(model.price_prompt_per_mtok_cents / 100),
    );
    if (!promptPrice) return;
    const completionPrice = window.prompt(
      t("输出单价（元 / MTok）"),
      String(model.price_completion_per_mtok_cents / 100),
    );
    if (!completionPrice) return;
    try {
      await api("/admin/inference/models/" + model.id, {
        method: "PATCH",
        body: JSON.stringify({
          version: model.version,
          price_prompt_per_mtok_cents: Math.round(Number(promptPrice) * 100),
          price_completion_per_mtok_cents: Math.round(Number(completionPrice) * 100),
          reason: "管理员调价",
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("调价失败"));
    }
  }

  async function createModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const model = await api<AdminInferenceModel>("/admin/inference/models", {
        method: "POST",
        body: JSON.stringify({
          slug: data.get("slug"),
          display_name: data.get("display_name"),
          description: data.get("description"),
          context_length: Number(data.get("context_length")),
          price_prompt_per_mtok_cents: Math.round(Number(data.get("prompt_price")) * 100),
          price_completion_per_mtok_cents: Math.round(
            Number(data.get("completion_price")) * 100,
          ),
          cost_prompt_per_mtok_cents: Math.round(Number(data.get("prompt_cost")) * 100),
          cost_completion_per_mtok_cents: Math.round(
            Number(data.get("completion_cost")) * 100,
          ),
          backend_type: data.get("backend_type"),
          status: "draft",
        }),
      });
      setShowModelForm(false);
      setSelectedModelId(model.id);
      await load();
      await loadReplicas(model.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建模型失败"));
    }
  }

  async function createReplica(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedModel) return;
    setError("");
    const data = new FormData(event.currentTarget);
    const credential = String(data.get("credential_env_var") ?? "").trim();
    const capacity = String(data.get("capacity_tpm") ?? "").trim();
    try {
      await api("/admin/inference/models/" + selectedModel.id + "/replicas", {
        method: "POST",
        body: JSON.stringify({
          label: data.get("label"),
          endpoint: data.get("endpoint"),
          upstream_model: data.get("upstream_model"),
          credential_env_var: credential || null,
          timeout_seconds: Number(data.get("timeout_seconds")),
          capacity_tpm: capacity ? Number(capacity) : null,
          weight: 100,
          enabled: true,
        }),
      });
      setShowReplicaForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建推理副本失败"));
    }
  }

  async function configureRouter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedModel?.is_auto_router) return;
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api("/admin/inference/models/" + selectedModel.id + "/auto-router", {
        method: "PUT",
        body: JSON.stringify({
          classifier_model_id: data.get("classifier_model_id"),
          simple_model_id: data.get("simple_model_id"),
          complex_model_id: data.get("complex_model_id"),
          fallback_tier: data.get("fallback_tier"),
          classifier_timeout_seconds: Number(data.get("classifier_timeout_seconds")),
          version: selectedModel.router_config?.version ?? null,
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("保存 Auto Router 失败"));
    }
  }

  async function checkHealth(replicaId: string) {
    setError("");
    try {
      await api("/admin/inference/replicas/" + replicaId + "/health-check", {
        method: "POST",
      });
      await loadReplicas(selectedModelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("健康检查失败"));
    }
  }

  return (
    <div className="workspace-content">
      <div className="workspace-title">
        <div>
          <h1>{t("模型 API 运营")}</h1>
          <p>{t("接入推理端点，并配置 Auto Router、Token 成本、售价、容量和发布状态。")}</p>
        </div>
        <Button
          variant="accent"
          onClick={() => setShowModelForm((visible) => !visible)}
        >
          <Plus size={16} /> {t("新建模型")}
        </Button>
      </div>

      <Alert className="mb-4"><AlertDescription>{t("端点凭据只填写环境变量名，不能在后台保存真实密钥。模型必须有健康副本才能上架。")}</AlertDescription></Alert>

      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}

      <AdminInferenceInfrastructure />

      {showModelForm && (
        <form className="panel" onSubmit={createModel}>
          <div className="panel-head"><h2>{t("登记模型 API")}</h2></div>
          <div className="form-grid">
            <div className="form-row"><Label>{t("公开模型 ID")}</Label><Input name="slug" placeholder="customer/qwen3-8b" required /></div>
            <div className="form-row"><Label>{t("显示名称")}</Label><Input name="display_name" placeholder="Qwen3 8B" required /></div>
            <div className="form-row"><Label>{t("上下文长度")}</Label><Input name="context_length" type="number" defaultValue="8192" required /></div>
            <div className="form-row"><Label>{t("说明")}</Label><Input name="description" placeholder={t("面向开发者的模型说明")} /></div>
            <div className="form-row"><Label>{t("模型类型")}</Label><NativeSelect name="backend_type" defaultValue="openai_compatible"><option value="openai_compatible">OpenAI-compatible</option><option value="auto_router">Auto Router</option></NativeSelect></div>
            <div className="form-row"><Label>{t("输入售价 元/MTok")}</Label><Input name="prompt_price" type="number" step="0.01" defaultValue="0.20" required /></div>
            <div className="form-row"><Label>{t("输出售价 元/MTok")}</Label><Input name="completion_price" type="number" step="0.01" defaultValue="0.50" required /></div>
            <div className="form-row"><Label>{t("输入成本 元/MTok")}</Label><Input name="prompt_cost" type="number" step="0.01" defaultValue="0.10" required /></div>
            <div className="form-row"><Label>{t("输出成本 元/MTok")}</Label><Input name="completion_cost" type="number" step="0.01" defaultValue="0.20" required /></div>
          </div>
          <Button variant="accent" style={{ marginTop: 16 }}>{t("保存草稿")}</Button>
        </form>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>{t("模型与售价")}</h2>
          <Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw /> {t("刷新")}</Button>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t("模型")}</th><th>{t("后端")}</th><th>{t("售价 / MTok")}</th><th>{t("成本 / MTok")}</th><th>{t("副本")}</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id}>
                  <td>
                    <Button variant="link" className="table-primary" onClick={() => { setSelectedModelId(model.id); void loadReplicas(model.id); }}>
                      {model.display_name}
                    </Button>
                    <div className="table-secondary mono">{model.slug}</div>
                  </td>
                  <td className="mono">{model.is_auto_router ? "Auto Router" : model.backend_type}</td>
                  <td>{money(model.price_prompt_per_mtok_cents)} / {money(model.price_completion_per_mtok_cents)}</td>
                  <td>{model.cost_prompt_per_mtok_cents == null ? t("无权限") : money(model.cost_prompt_per_mtok_cents) + " / " + money(model.cost_completion_per_mtok_cents ?? 0)}</td>
                  <td>{model.replica_count}</td>
                  <td><StatusPill status={model.status} /></td>
                  <td><div style={{ display: "flex", gap: 6 }}><Button variant="outline" size="sm" onClick={() => void editPrice(model)}>{t("调价")}</Button><Button variant="outline" size="sm" onClick={() => void toggle(model)}>{t(model.status === "published" ? "下架" : "上架")}</Button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedModel?.is_auto_router && (
        <section className="panel">
          <div className="panel-head">
            <div><h2>{selectedModel.display_name} · {t("路由策略")}</h2><p className="table-secondary">{t("判断器只返回 simple / complex；失败时走配置的保底档位。")}</p></div>
          </div>
          {directModels.length < 2 ? (
            <Alert><AlertDescription>{t("至少需要两个已上架且健康的直接模型，才能配置简单与复杂档位。")}</AlertDescription></Alert>
          ) : (
            <form key={`${selectedModel.id}-${selectedModel.router_config?.version ?? 0}`} onSubmit={configureRouter}>
              <div className="form-grid">
                <div className="form-row"><Label>{t("小型判断模型")}</Label><NativeSelect name="classifier_model_id" defaultValue={selectedModel.router_config?.classifier_model_id ?? directModels[0]?.id} required>{directModels.map((model) => <option key={model.id} value={model.id}>{model.display_name} · {model.slug}</option>)}</NativeSelect></div>
                <div className="form-row"><Label>{t("简单任务模型")}</Label><NativeSelect name="simple_model_id" defaultValue={selectedModel.router_config?.simple_model_id ?? directModels[0]?.id} required>{directModels.map((model) => <option key={model.id} value={model.id}>{model.display_name} · {model.slug}</option>)}</NativeSelect></div>
                <div className="form-row"><Label>{t("复杂任务模型")}</Label><NativeSelect name="complex_model_id" defaultValue={selectedModel.router_config?.complex_model_id ?? directModels[1]?.id} required>{directModels.map((model) => <option key={model.id} value={model.id}>{model.display_name} · {model.slug}</option>)}</NativeSelect></div>
                <div className="form-row"><Label>{t("判断失败保底")}</Label><NativeSelect name="fallback_tier" defaultValue={selectedModel.router_config?.fallback_tier ?? "complex"}><option value="complex">{t("复杂模型（质量优先）")}</option><option value="simple">{t("简单模型（成本优先）")}</option></NativeSelect></div>
                <div className="form-row"><Label>{t("判断超时秒数")}</Label><Input name="classifier_timeout_seconds" type="number" min="1" max="30" defaultValue={selectedModel.router_config?.classifier_timeout_seconds ?? 5} required /></div>
              </div>
              <Button variant="accent" style={{ marginTop: 14 }}>{t("保存路由策略")}</Button>
            </form>
          )}
        </section>
      )}

      {selectedModel && !selectedModel.is_auto_router && (
        <section className="panel">
          <div className="panel-head">
            <div><h2>{selectedModel.display_name} · {t("推理副本")}</h2><p className="table-secondary">{t("内部端点和凭据引用只在运营后台显示。")}</p></div>
            <Button variant="accent" size="sm" onClick={() => setShowReplicaForm((visible) => !visible)}><ServerCog /> {t("添加副本")}</Button>
          </div>
          {showReplicaForm && (
            <form onSubmit={createReplica} style={{ marginBottom: 20 }}>
              <div className="form-grid">
                <div className="form-row"><Label>{t("副本标签")}</Label><Input name="label" placeholder="shanghai-a" required /></div>
                <div className="form-row"><Label>API base URL</Label><Input name="endpoint" placeholder="https://vllm.internal/v1" required /></div>
                <div className="form-row"><Label>{t("上游模型 ID")}</Label><Input name="upstream_model" placeholder="Qwen/Qwen3-8B" required /></div>
                <div className="form-row"><Label>{t("凭据环境变量")}</Label><Input name="credential_env_var" placeholder="VLLM_API_KEY" /></div>
                <div className="form-row"><Label>{t("超时秒数")}</Label><Input name="timeout_seconds" type="number" defaultValue="120" required /></div>
                <div className="form-row"><Label>{t("容量 TPM")}</Label><Input name="capacity_tpm" type="number" placeholder="120000" /></div>
              </div>
              <Button variant="accent" style={{ marginTop: 14 }}>{t("保存副本")}</Button>
            </form>
          )}
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>{t("副本")}</th><th>{t("内部端点")}</th><th>{t("上游模型")}</th><th>{t("容量")}</th><th>{t("健康")}</th><th>{t("操作")}</th></tr></thead>
              <tbody>
                {replicas.map((replica) => (
                  <tr key={replica.id}>
                    <td><div className="table-primary">{replica.label}</div><div className="table-secondary">{t("权重")} {replica.weight} · {t("超时")} {replica.timeout_seconds}s</div></td>
                    <td className="mono">{replica.endpoint}</td>
                    <td className="mono">{replica.upstream_model}</td>
                    <td>{replica.capacity_tpm == null ? t("未声明") : replica.capacity_tpm.toLocaleString() + " TPM"}</td>
                    <td><StatusPill status={replica.health_status} /></td>
                    <td><Button variant="outline" size="sm" onClick={() => void checkHealth(replica.id)}>{t("健康检查")}</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-head"><h2>{t("最近 Token 用量")}</h2></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t("用户")}</th><th>{t("模型")}</th><th>{t("输入/输出")}</th><th>{t("扣费")}</th><th>{t("状态")}</th></tr></thead>
            <tbody>
              {usage.slice(0, 50).map((row) => (
                <tr key={row.id}><td className="mono">{row.user_id}</td><td className="mono">{row.model_slug}{row.routed_model_slug ? ` → ${row.routed_model_slug}` : ""}</td><td>{row.prompt_tokens}/{row.completion_tokens}</td><td>{money(row.debit_cents)}</td><td>{row.routing_tier ?? row.status}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
