"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, Send } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { api, money } from "@/lib/api";
import type {
  Conversation,
  ConversationDetail,
  ConversationSendResponse,
  InferenceModel,
  User,
} from "@/lib/types";
import { usePreferences } from "./PreferencesProvider";

export function ChatClient() {
  const { t } = usePreferences();
  const router = useRouter();
  const params = useSearchParams();
  const initialModel = params.get("model") || "opencompute/auto";
  const [user, setUser] = useState<User | null>(null);
  const [models, setModels] = useState<InferenceModel[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [modelSlug, setModelSlug] = useState(initialModel);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadLists = useCallback(async () => {
    const [me, catalog, rows] = await Promise.all([
      api<User>("/auth/me"),
      api<InferenceModel[]>("/inference/models"),
      api<Conversation[]>("/inference/conversations"),
    ]);
    setUser(me);
    setModels(catalog);
    setConversations(rows);
    if (!catalog.find((item) => item.slug === modelSlug) && catalog[0]) {
      setModelSlug(catalog[0].slug);
    }
  }, [modelSlug]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadLists().catch((err: { status?: number; message?: string }) => {
        if (err?.status === 401) {
          router.replace(`/login?next=${encodeURIComponent("/chat")}`);
          return;
        }
        setError(err.message || t("加载失败"));
      });
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [loadLists, router, t]);

  const openConversation = useCallback(async (id: string) => {
    setActiveId(id);
    const row = await api<ConversationDetail>(`/inference/conversations/${id}`);
    setDetail(row);
    setModelSlug(row.model_slug);
  }, []);

  async function createConversation() {
    setBusy(true);
    setError("");
    try {
      const row = await api<Conversation>("/inference/conversations", {
        method: "POST",
        body: JSON.stringify({ model_slug: modelSlug, title: t("新对话") }),
      });
      await loadLists();
      await openConversation(row.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("创建失败"));
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim()) return;
    setBusy(true);
    setError("");
    try {
      let conversationId = activeId;
      if (!conversationId) {
        const row = await api<Conversation>("/inference/conversations", {
          method: "POST",
          body: JSON.stringify({ model_slug: modelSlug, title: t("新对话") }),
        });
        conversationId = row.id;
        setActiveId(row.id);
      }
      const result = await api<ConversationSendResponse>(
        `/inference/conversations/${conversationId}/messages`,
        { method: "POST", body: JSON.stringify({ content: draft.trim() }) },
      );
      setDraft("");
      await loadLists();
      setDetail((prev) => {
        if (!prev || prev.id !== conversationId) {
          return {
            id: conversationId!,
            title: draft.trim().slice(0, 40) || t("新对话"),
            model_slug: modelSlug,
            status: "active",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            messages: [result.user_message, result.assistant_message],
          };
        }
        return {
          ...prev,
          messages: [...prev.messages, result.user_message, result.assistant_message],
        };
      });
      const me = await api<User>("/auth/me");
      setUser(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("发送失败"));
    } finally {
      setBusy(false);
    }
  }

  const activeTitle = useMemo(
    () => detail?.title || conversations.find((item) => item.id === activeId)?.title || t("新对话"),
    [activeId, conversations, detail, t],
  );

  return (
    <div className="chat-layout">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-head">
          <strong>Open Compute System</strong>
          <Button variant="accent" size="sm" disabled={busy} onClick={() => void createConversation()}><Plus />{t("新对话")}</Button>
        </div>
        <div className="chat-conv-list">
          {conversations.map((item) => (
            <Button
              key={item.id}
              variant="ghost"
              className={`chat-conv-item ${item.id === activeId ? "active" : ""}`}
              onClick={() => void openConversation(item.id).catch((err) => setError(err.message))}
            >
              <div className="table-primary">{item.title}</div>
              <div className="table-secondary mono">{item.model_slug}</div>
            </Button>
          ))}
        </div>
      </aside>
      <section className="chat-main">
        <header className="chat-top">
          <div>
            <p className="eyebrow">CHAT</p>
            <h1>{activeTitle}</h1>
            <p className="table-secondary">{t("余额")} {user ? money(user.balance_cents) : "—"} · {t("历史保存在服务器")}</p>
          </div>
          <NativeSelect value={modelSlug} onChange={(e) => setModelSlug(e.target.value)} disabled={!!activeId} aria-label={t("当前模型")}>
            {models.map((model) => (
              <option key={model.id} value={model.slug}>
                {model.display_name}
              </option>
            ))}
          </NativeSelect>
        </header>
        {error && (
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
        )}
        <div className="chat-messages">
          {(detail?.messages ?? []).map((message) => (
            <div className={`chat-bubble ${message.role}`} key={message.id}>
              <div className="table-secondary">{message.role}</div>
              <div>{message.content}</div>
            </div>
          ))}
          {!detail?.messages?.length && <div className="empty-state"><h3>{t("开始一段 Open Compute System 对话")}</h3><p>{t("当前为 Mock 推理，不代表真实 GPU 交付。")}</p></div>}
        </div>
        <form className="chat-composer" onSubmit={sendMessage}>
          <Textarea
            rows={3}
            value={draft}
            placeholder={t("输入消息…")}
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button variant="accent" disabled={busy || !draft.trim()}><Send />{t("发送")}</Button>
        </form>
      </section>
    </div>
  );
}
