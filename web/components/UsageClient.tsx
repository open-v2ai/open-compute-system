"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { api, formatDate, money } from "@/lib/api";
import type { UsageEvent } from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function UsageClient() {
  const { t } = usePreferences();
  const [rows, setRows] = useState<UsageEvent[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void api<UsageEvent[]>("/inference/usage")
        .then(setRows)
        .catch((err) => setError(err.message));
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);
  const totalDebit = rows.reduce((sum, row) => sum + row.debit_cents, 0);
  return (
    <div className="workspace-content">
      <div className="workspace-title">
        <div>
          <h1>{t("Token 用量")}</h1>
          <p>{t("输入、输出 Token、模型副本、延迟和扣费均来自统一推理网关。")}</p>
        </div>
        <Card className="stat-card" style={{ minWidth: 180 }}>
          <small>{t("本页合计扣费")}</small>
          <strong>{money(totalDebit)}</strong>
        </Card>
      </div>
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <Card className="panel">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("时间")}</th>
                <th>{t("模型")}</th>
                <th>Tokens</th>
                <th>{t("延迟")}</th>
                <th>{t("扣费")}</th>
                <th>{t("副本")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{formatDate(row.created_at)}</td>
                  <td className="mono">{row.model_slug}</td>
                  <td>
                    {row.prompt_tokens} / {row.completion_tokens}
                  </td>
                  <td>{row.latency_ms} ms</td>
                  <td>{money(row.debit_cents)}</td>
                  <td>{row.replica_label || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
