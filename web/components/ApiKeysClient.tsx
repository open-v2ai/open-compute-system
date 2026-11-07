"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { exampleApiBaseUrl } from "@/lib/deployment";
import { api, formatDate, money } from "@/lib/api";
import type { ApiKey, ApiKeyCreated, InferenceModel } from "@/lib/types";
import { StatusPill } from "./StatusPill";
import { usePreferences } from "./PreferencesProvider";

export function ApiKeysClient() {
  const { t } = usePreferences();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [models, setModels] = useState<InferenceModel[]>([]);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [name, setName] = useState(t("默认 Key"));
  const [rpmLimit, setRpmLimit] = useState(60);
  const [tpmLimit, setTpmLimit] = useState(100000);
  const [allowedModel, setAllowedModel] = useState("");
  const load = useCallback(async () => {
    try {
      const [keyRows, modelRows] = await Promise.all([
        api<ApiKey[]>("/inference/keys"),
        api<InferenceModel[]>("/inference/models"),
      ]);
      setKeys(keyRows);
      setModels(modelRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("加载失败"));
    }
  }, [t]);
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await api<ApiKeyCreated>("/inference/keys", {
        method: "POST",
        body: JSON.stringify({
          name,
          rpm_limit: rpmLimit,
          tpm_limit: tpmLimit,
          allowed_models: allowedModel ? [allowedModel] : [],
        }),
      });
      setSecret(created.secret);
      setName(t("默认 Key"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建失败"));
    }
  }

  async function revoke(id: string) {
    setError("");
    try {
      await api(`/inference/keys/${id}/revoke`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("吊销失败"));
    }
  }

  return (
    <div className="workspace-content">
      <div className="workspace-title">
        <div>
          <h1>API Keys</h1>
          <p>{t("Open Compute System · base_url 使用 /api/v1，模型如 opencompute/qwen3-8b。")}</p>
        </div>
      </div>
      <Card className="panel"><form onSubmit={create}>
        <div className="panel-head">
          <h2>{t("创建 Key")}</h2>
        </div>
        <div className="form-row">
          <Label>{t("名称")}</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <div className="form-row">
            <Label>{t("RPM 上限")}</Label>
            <Input type="number" min="1" max="600" value={rpmLimit} onChange={(e) => setRpmLimit(Number(e.target.value))} />
          </div>
          <div className="form-row">
            <Label>{t("TPM 上限")}</Label>
            <Input type="number" min="1" value={tpmLimit} onChange={(e) => setTpmLimit(Number(e.target.value))} />
          </div>
          <div className="form-row">
            <Label>{t("允许模型")}</Label>
            <NativeSelect value={allowedModel} onChange={(e) => setAllowedModel(e.target.value)}>
              <option value="">{t("全部已发布模型")}</option>
              {models.map((model) => <option value={model.slug} key={model.id}>{model.display_name}</option>)}
            </NativeSelect>
          </div>
        </div>
        <Button variant="accent" style={{ marginTop: 14 }}>{t("创建")}</Button>
        {secret && (
          <Alert variant="warning" className="mt-3.5"><AlertDescription>{t("请立即复制，仅显示一次：")}<code className="mono">{secret}</code></AlertDescription></Alert>
        )}
      </form></Card>
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <Card className="panel">
        <div className="panel-head">
          <h2>{t("我的 Keys")}</h2>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("名称")}</th>
                <th>{t("前缀")}</th>
                <th>{t("已用")}</th>
                <th>{t("限额")}</th>
                <th>{t("速率")}</th>
                <th>{t("模型范围")}</th>
                <th>{t("状态")}</th>
                <th>{t("创建")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td className="mono">{key.key_prefix}…</td>
                  <td>{money(key.spent_cents)}</td>
                  <td>{key.credit_limit_cents == null ? t("不限") : money(key.credit_limit_cents)}</td>
                  <td>{key.rpm_limit} RPM · {key.tpm_limit.toLocaleString()} TPM</td>
                  <td>{key.allowed_models.length === 0 ? t("全部") : key.allowed_models.join(", ")}</td>
                  <td><StatusPill status={key.status} /></td>
                  <td>{formatDate(key.created_at)}</td>
                  <td>
                    {key.status === "active" && (
                      <Button variant="destructive" size="sm" onClick={() => void revoke(key.id)}>{t("吊销")}</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="panel">
        <div className="panel-head">
          <h2>{t("SDK 示例")}</h2>
        </div>
        <pre className="mono" style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.6 }}>
{`from openai import OpenAI
client = OpenAI(base_url="${exampleApiBaseUrl()}", api_key="ocs_...")
client.chat.completions.create(
  model="opencompute/qwen3-8b",
  messages=[{"role":"user","content":"hello"}],
)`}
        </pre>
      </Card>
    </div>
  );
}
