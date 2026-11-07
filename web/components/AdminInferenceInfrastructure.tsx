"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Container, Plus, RefreshCw, ServerCog, Square } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import type {
  AdminInferenceModel,
  InferenceDeployment,
  InferenceNode,
} from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function AdminInferenceInfrastructure() {
  const { t } = usePreferences();
  const [nodes, setNodes] = useState<InferenceNode[]>([]);
  const [deployments, setDeployments] = useState<InferenceDeployment[]>([]);
  const [models, setModels] = useState<AdminInferenceModel[]>([]);
  const [showNodeForm, setShowNodeForm] = useState(false);
  const [showDeploymentForm, setShowDeploymentForm] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [nodeRows, deploymentRows, modelRows] = await Promise.all([
      api<InferenceNode[]>("/admin/inference/nodes"),
      api<InferenceDeployment[]>("/admin/inference/deployments"),
      api<AdminInferenceModel[]>("/admin/inference/models"),
    ]);
    setNodes(nodeRows);
    setDeployments(deploymentRows);
    setModels(modelRows);
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void load().catch((err: Error) => setError(err.message));
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  async function createNode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api("/admin/inference/nodes", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          agent_url: data.get("agent_url"),
          agent_token_env_var: data.get("agent_token_env_var"),
          runtime_credential_env_var: data.get("runtime_credential_env_var"),
        }),
      });
      setShowNodeForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建节点失败"));
    }
  }

  async function checkNode(nodeId: string) {
    setError("");
    try {
      await api("/admin/inference/nodes/" + nodeId + "/health-check", {
        method: "POST",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("节点健康检查失败"));
      await load().catch(() => undefined);
    }
  }

  async function createDeployment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    const gpuIds = String(data.get("gpu_device_ids") ?? "")
      .split(",")
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value));
    const image = String(data.get("image") ?? "").trim();
    const maxModelLen = String(data.get("max_model_len") ?? "").trim();
    const hfTokenEnv = String(data.get("huggingface_token_env_var") ?? "").trim();
    try {
      await api("/admin/inference/deployments", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          model_id: data.get("model_id"),
          node_id: data.get("node_id"),
          model_source_id: data.get("model_source_id"),
          served_model_name: data.get("served_model_name"),
          image: image || null,
          gpu_device_ids: gpuIds,
          tensor_parallel_size: gpuIds.length,
          host_port: Number(data.get("host_port")),
          max_model_len: maxModelLen ? Number(maxModelLen) : null,
          gpu_memory_utilization: 0.9,
          huggingface_token_env_var: hfTokenEnv || null,
        }),
      });
      setShowDeploymentForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建 vLLM 部署失败"));
    }
  }

  async function deploymentAction(deploymentId: string, action: "sync" | "stop") {
    setError("");
    try {
      await api("/admin/inference/deployments/" + deploymentId + "/" + action, {
        method: "POST",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("部署操作失败"));
      await load().catch(() => undefined);
    }
  }

  const deployableModels = models.filter(
    (model) => model.backend_type === "openai_compatible",
  );
  const healthyNodes = nodes.filter((node) => node.status === "healthy" && node.enabled);

  return (
    <>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>{t("私有 GPU 节点")}</h2>
            <p className="table-secondary">
              {t("控制面只保存 Agent URL 和环境变量名，不保存 Agent Token 或 vLLM Key。")}
            </p>
          </div>
          <Button
            variant="accent"
            size="sm"
            onClick={() => setShowNodeForm((visible) => !visible)}
          >
            <Plus size={14} /> {t("添加节点")}
          </Button>
        </div>

        {showNodeForm && (
          <form onSubmit={createNode} style={{ marginBottom: 20 }}>
            <div className="form-grid">
              <div className="form-row"><Label>{t("节点名称")}</Label><Input name="name" placeholder={t("上海 GPU 节点 A")} required /></div>
              <div className="form-row"><Label>Agent URL</Label><Input name="agent_url" placeholder="http://10.0.0.8:8110" required /></div>
              <div className="form-row"><Label>{t("Agent Token 环境变量")}</Label><Input name="agent_token_env_var" defaultValue="PRIVATE_NODE_AGENT_TOKEN" required /></div>
              <div className="form-row"><Label>{t("vLLM Key 环境变量")}</Label><Input name="runtime_credential_env_var" defaultValue="VLLM_INTERNAL_API_KEY" required /></div>
            </div>
            <Button variant="accent" style={{ marginTop: 14 }}>{t("保存节点")}</Button>
          </form>
        )}

        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t("节点")}</th><th>Agent</th><th>Docker</th><th>GPU</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead>
            <tbody>
              {nodes.map((node) => (
                <tr key={node.id}>
                  <td><div className="table-primary">{node.name}</div><div className="table-secondary mono">{node.id}</div></td>
                  <td className="mono">{node.agent_url}</td>
                  <td>{node.docker_version ?? t("未检查")}</td>
                  <td>{node.gpu_summary.length === 0 ? t("未发现") : node.gpu_summary.map((gpu) => String(gpu.name ?? "GPU") + " #" + String(gpu.index ?? "?")).join(", ")}</td>
                  <td><StatusPill status={node.status} /></td>
                  <td><Button variant="outline" size="sm" onClick={() => void checkNode(node.id)}><RefreshCw /> {t("健康检查")}</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>{t("Docker vLLM 部署")}</h2>
            <p className="table-secondary">
              {t("首期只允许受控 vLLM 模板；Kubernetes 后续接入同一部署接口。")}
            </p>
          </div>
          <Button
            variant="accent"
            size="sm"
            disabled={healthyNodes.length === 0 || deployableModels.length === 0}
            onClick={() => setShowDeploymentForm((visible) => !visible)}
          >
            <Container size={14} /> {t("创建部署")}
          </Button>
        </div>

        {showDeploymentForm && (
          <form onSubmit={createDeployment} style={{ marginBottom: 20 }}>
            <div className="form-grid">
              <div className="form-row"><Label>{t("平台模型")}</Label><NativeSelect name="model_id" required>{deployableModels.map((model) => <option value={model.id} key={model.id}>{model.display_name}</option>)}</NativeSelect></div>
              <div className="form-row"><Label>{t("GPU 节点")}</Label><NativeSelect name="node_id" required>{healthyNodes.map((node) => <option value={node.id} key={node.id}>{node.name}</option>)}</NativeSelect></div>
              <div className="form-row"><Label>{t("模型来源 ID")}</Label><Input name="model_source_id" placeholder="Qwen/Qwen3-8B" required /></div>
              <div className="form-row"><Label>{t("对外模型 ID")}</Label><Input name="served_model_name" placeholder="customer/qwen3-8b" required /></div>
              <div className="form-row"><Label>{t("GPU IDs（逗号分隔）")}</Label><Input name="gpu_device_ids" defaultValue="0" required /></div>
              <div className="form-row"><Label>{t("宿主机端口")}</Label><Input name="host_port" type="number" defaultValue="18080" required /></div>
              <div className="form-row"><Label>Max model length</Label><Input name="max_model_len" type="number" defaultValue="8192" /></div>
              <div className="form-row"><Label>{t("vLLM 镜像（可选）")}</Label><Input name="image" placeholder="vllm/vllm-openai:latest" /></div>
              <div className="form-row"><Label>{t("HF Token 环境变量（可选）")}</Label><Input name="huggingface_token_env_var" placeholder="HF_TOKEN" /></div>
            </div>
            <Button variant="accent" style={{ marginTop: 14 }}>{t("启动 vLLM")}</Button>
          </form>
        )}

        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t("部署")}</th><th>{t("模型来源")}</th><th>GPU</th><th>Endpoint</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead>
            <tbody>
              {deployments.map((deployment) => (
                <tr key={deployment.id}>
                  <td><div className="table-primary">{deployment.served_model_name}</div><div className="table-secondary mono">{deployment.id}</div></td>
                  <td className="mono">{deployment.model_source_id}</td>
                  <td>{deployment.gpu_device_ids.join(", ")} · TP {deployment.tensor_parallel_size}</td>
                  <td className="mono">{deployment.endpoint ?? t("等待 Agent")}</td>
                  <td><StatusPill status={deployment.status} /></td>
                  <td><div style={{ display: "flex", gap: 6 }}><Button variant="outline" size="sm" onClick={() => void deploymentAction(deployment.id, "sync")}><ServerCog /> {t("同步")}</Button>{!["stopped", "failed"].includes(deployment.status) && <Button variant="destructive" size="sm" onClick={() => void deploymentAction(deployment.id, "stop")}><Square /> {t("停止")}</Button>}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
