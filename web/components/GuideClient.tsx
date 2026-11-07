"use client";

import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  ClipboardCheck,
  CloudCog,
  Cpu,
  KeyRound,
  LifeBuoy,
  Search,
  ServerCog,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { exampleApiBaseUrl } from "@/lib/deployment";
import { SiteShell } from "@/components/SiteShell";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

type Copy = { zh: string; en: string };
type Category = "all" | "api" | "gpu" | "operations";

type Guide = {
  id: string;
  category: Exclude<Category, "all">;
  icon: LucideIcon;
  title: Copy;
  description: Copy;
  steps: Copy[];
  href: string;
  action: Copy;
  code?: string;
};

const c = (zh: string, en: string): Copy => ({ zh, en });

const categories: Array<{ id: Category; label: Copy }> = [
  { id: "all", label: c("全部", "All") },
  { id: "api", label: c("模型 API", "Model API") },
  { id: "gpu", label: c("GPU 实例", "GPU instances") },
  { id: "operations", label: c("运营接入", "Operations") },
];

const quickStart = [
  { id: "account", label: c("登录或注册算力账号", "Sign in or create a compute account"), href: "/login" },
  { id: "model", label: c("在模型目录确认可用模型", "Choose an available model from the catalog"), href: "/models" },
  { id: "key", label: c("创建 API Key 并设置模型权限", "Create an API key and set model access"), href: "/console/keys" },
  { id: "call", label: c("复制示例，完成第一次模型调用", "Copy the example and make your first model call"), href: "#api-call" },
];

const guides: Guide[] = [
  {
    id: "api-key",
    category: "api",
    icon: KeyRound,
    title: c("创建并保护 API Key", "Create and protect an API key"),
    description: c("为不同应用拆分 Key，分别设置模型范围、RPM、TPM 和额度。", "Use separate keys for each app, with individual model, RPM, TPM, and credit limits."),
    steps: [
      c("登录控制台，进入 API Keys。", "Sign in to the console and open API Keys."),
      c("填写用途名称、速率限制和允许调用的模型。", "Set a purpose, rate limits, and allowed models."),
      c("只在创建时复制完整密钥，不要写进仓库或前端代码。", "Copy the full secret when created; never commit it or expose it in browser code."),
    ],
    href: "/console/keys",
    action: c("管理 API Keys", "Manage API keys"),
  },
  {
    id: "api-call",
    category: "api",
    icon: Terminal,
    title: c("完成第一次模型调用", "Make your first model call"),
    description: c("接口兼容 OpenAI Chat Completions；部署域名替换示例中的本地地址。", "The API is compatible with OpenAI Chat Completions. Replace the local URL with your deployment domain."),
    steps: [
      c("把 OCS_API_KEY 替换为控制台创建的密钥。", "Replace OCS_API_KEY with the key created in the console."),
      c("从模型目录复制已上架的公开模型 ID。", "Copy a published public model ID from the catalog."),
      c("生产调用应生成唯一 X-Request-ID，便于幂等结算和排障。", "Use a unique X-Request-ID in production for idempotent billing and troubleshooting."),
    ],
    href: "/models",
    action: c("查看模型目录", "Open model catalog"),
    code: `curl ${exampleApiBaseUrl()}/chat/completions \\
  -H "Authorization: Bearer OCS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -H "X-Request-ID: req_first_call" \\
  -d '{
    "model": "opencompute/qwen3-8b",
    "messages": [{"role": "user", "content": "你好"}]
  }'`,
  },
  {
    id: "gpu-instance",
    category: "gpu",
    icon: Cpu,
    title: c("创建并连接 GPU 实例", "Create and connect to a GPU instance"),
    description: c("从库存选择 SKU，确认镜像和计费周期，再跟踪异步交付状态。", "Choose an in-stock SKU, confirm the image and billing period, then follow asynchronous provisioning."),
    steps: [
      c("在算力市场按型号、区域、库存和价格筛选。", "Filter the marketplace by model, region, stock, and price."),
      c("创建前确认镜像、实例名称和预计扣款。", "Confirm the image, instance name, and estimated charge."),
      c("实例进入 running 后再复制 SSH 或打开 JupyterLab。", "Wait for the running state before copying SSH details or opening JupyterLab."),
    ],
    href: "/market",
    action: c("浏览算力市场", "Browse GPU marketplace"),
  },
  {
    id: "lifecycle",
    category: "gpu",
    icon: Boxes,
    title: c("管理实例生命周期", "Manage the instance lifecycle"),
    description: c("开机、关机和释放都是异步任务；释放会永久删除演示磁盘。", "Start, stop, and release are asynchronous tasks. Release permanently deletes demo disks."),
    steps: [
      c("先刷新状态，避免对仍在变更中的实例重复操作。", "Refresh status before acting on an instance that may still be changing."),
      c("关机后当前演示会释放 GPU 库存，但不代表已实现精确按秒计费。", "The demo releases GPU stock after shutdown, but does not provide exact per-second billing."),
      c("释放前保存需要的数据；该操作不可撤销。", "Save required data before release; this action cannot be undone."),
    ],
    href: "/console/instances",
    action: c("查看我的实例", "View my instances"),
  },
  {
    id: "connect-runtime",
    category: "operations",
    icon: ServerCog,
    title: c("接入模型端点", "Connect a model endpoint"),
    description: c("登记 vLLM、NIM 或其他 OpenAI-compatible 端点，通过健康检查后再上架。", "Register a vLLM, NIM, or other OpenAI-compatible endpoint and publish it only after health checks pass."),
    steps: [
      c("在运营后台创建公开模型并设置输入、输出 Token 售价。", "Create a public model in operations admin and set prompt and completion prices."),
      c("添加副本、上游模型 ID 和凭据环境变量，不录入明文密钥。", "Add a replica, upstream model ID, and credential environment variable without storing plaintext secrets."),
      c("验证健康、故障切换和真实 Token 用量对账后再用于生产。", "Verify health, failover, and real token reconciliation before production use."),
    ],
    href: "/admin/inference",
    action: c("进入模型运营", "Open model operations"),
  },
  {
    id: "connect-gpu",
    category: "operations",
    icon: CloudCog,
    title: c("接入自己的 GPU", "Connect your own GPUs"),
    description: c("通过受控 Provider 与节点 Agent 纳管资源，权限、订单和计费仍由平台服务端处理。", "Manage resources through controlled providers and node agents while authorization, orders, and billing remain server-side."),
    steps: [
      c("实现 ResourceProvider，并在 factory 注册稳定的 access_mode。", "Implement ResourceProvider and register a stable access_mode in the factory."),
      c("在后台创建资源来源、配置凭据环境变量并绑定 SKU。", "Create the resource source, configure credential environment variables, and bind an SKU."),
      c("在真实 Docker/NVIDIA 环境验收创建、停止、失败退款和重复任务。", "Validate create, stop, failure refund, and repeated tasks in a real Docker/NVIDIA environment."),
    ],
    href: "/admin/resources",
    action: c("管理资源来源", "Manage resource providers"),
  },
];

const faqs = [
  [c("Token 怎样计量和扣费？", "How are tokens metered and billed?"), c("平台记录推理运行时返回的输入与输出 Token，并按模型售价结算。请求 ID 支持幂等；真实端点仍需完成用量对账。", "The platform records prompt and completion tokens returned by the runtime and bills at the model price. Request IDs support idempotency, and real endpoints still require usage reconciliation.")],
  [c("关机后还会计费吗？", "Am I billed after shutdown?"), c("当前按量演示在关机后释放 GPU 库存，但这不是精确到秒的生产计费，也没有真实支付渠道。", "The current demo releases GPU stock after shutdown, but it is not production per-second billing and no real payment channel is connected.")],
  [c("MockProvider 的 SSH 地址能连接吗？", "Can I connect to a MockProvider SSH address?"), c("不能把它当作真机地址。MockProvider 只验证平台业务流程；真实 SSH、Jupyter、GPU 和网络必须在外部环境单独验收。", "Do not treat it as a real host. MockProvider validates the platform workflow only; real SSH, Jupyter, GPU, and networking require separate external acceptance.")],
  [c("本地网页 Chat 能直接用于生产吗？", "Can the local web Chat be used in production?"), c("不能。本地种子模型仍是 Mock。生产需要真实端点、凭据、健康检查、Token 对账，以及 Redis RPM/TPM 限流验收。", "No. The local seeded model still uses Mock. Production requires a real endpoint, credentials, health checks, token reconciliation, and verified Redis RPM/TPM rate limiting.")],
];

function progressWidth(value: number) {
  return `${value}%`;
}

export function GuideClient() {
  const { locale } = usePreferences();
  const language = locale === "en-US" ? "en" : "zh";
  const text = (value: Copy) => value[language];
  const [category, setCategory] = useState<Category>("all");
  const [query, setQuery] = useState("");
  const [completed, setCompleted] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState<string | null>(null);

  const keyword = query.trim().toLocaleLowerCase();
  const filteredGuides = guides.filter((guide) => {
    if (category !== "all" && guide.category !== category) return false;
    if (!keyword) return true;
    const haystack = [text(guide.title), text(guide.description), ...guide.steps.map(text)].join(" ").toLocaleLowerCase();
    return haystack.includes(keyword);
  });

  const completedCount = quickStart.filter((item) => completed[item.id]).length;
  const progress = Math.round((completedCount / quickStart.length) * 100);

  async function copyCode(id: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(id);
      window.setTimeout(() => setCopied((current) => (current === id ? null : current)), 1800);
    } catch {
      setCopied(null);
    }
  }

  return (
    <SiteShell>
      <section className="page-hero">
        <div className="container">
          <p className="eyebrow">{language === "zh" ? "使用指南" : "GUIDE"}</p>
          <h1 className="page-title">
            {language === "zh" ? "从第一次登录，" : "From first sign-in"}
            <br />
            {language === "zh" ? "到跑通一次调用。" : "to your first working call."}
          </h1>
          <p>
            {language === "zh"
              ? "这里集中说明模型 API、GPU 实例、运营接入和产品边界；可以搜索步骤、记录上手进度，并直接复制调用示例。"
              : "Find model API, GPU instance, operations, and product-boundary guidance in one place. Search steps, track progress, and copy a working request."}
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild variant="accent"><Link href="#quick-start">{language === "zh" ? "开始上手" : "Get started"}<ArrowRight /></Link></Button>
            <Button asChild variant="outline"><Link href="#about">{language === "zh" ? "了解平台边界" : "Understand the boundaries"}</Link></Button>
          </div>
        </div>
      </section>

      <section id="quick-start" className="section-compact scroll-mt-24">
        <div className="container grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,.65fr)]">
          <Card className="overflow-hidden">
            <CardHeader className="flex-row items-center justify-between gap-4 border-b border-border bg-muted/45 pb-6">
              <div>
                <Badge variant="success">{language === "zh" ? "建议路径" : "Recommended path"}</Badge>
                <CardTitle className="mt-3 text-2xl">{language === "zh" ? "四步完成首次调用" : "Your first call in four steps"}</CardTitle>
                <CardDescription className="mt-2">{language === "zh" ? "勾选完成项，进度会在当前页面中实时更新。" : "Check off each item to update progress on this page."}</CardDescription>
              </div>
              <div className="min-w-24 text-right">
                <strong className="text-3xl tracking-tight">{progress}%</strong>
                <p className="mt-1 text-xs text-muted-foreground">{completedCount} / {quickStart.length}</p>
              </div>
            </CardHeader>
            <div className="h-1.5 bg-muted"><div className="h-full bg-accent transition-[width] duration-300" style={{ width: progressWidth(progress) }} /></div>
            <CardContent className="divide-y divide-border py-0">
              {quickStart.map((item, index) => (
                <div className="flex items-center gap-4 py-4" key={item.id}>
                  <Checkbox
                    id={`quick-${item.id}`}
                    checked={Boolean(completed[item.id])}
                    onCheckedChange={(checked) => setCompleted((current) => ({ ...current, [item.id]: checked === true }))}
                    aria-label={text(item.label)}
                  />
                  <label className="min-w-0 flex-1 cursor-pointer text-sm font-semibold" htmlFor={`quick-${item.id}`}>
                    <span className="mr-2 text-muted-foreground">0{index + 1}</span>{text(item.label)}
                  </label>
                  <Button asChild variant="ghost" size="icon-sm"><Link href={item.href} aria-label={`${text(item.label)} — ${language === "zh" ? "打开" : "open"}`}><ArrowRight /></Link></Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-foreground bg-foreground text-background">
            <CardHeader>
              <BookOpen className="size-8 text-accent" />
              <CardTitle className="mt-5 text-2xl">{language === "zh" ? "先确认你要做什么" : "Start with your goal"}</CardTitle>
              <CardDescription className="text-background/65">{language === "zh" ? "普通用户从模型目录或算力市场开始；资源运营方从后台接入端点和 GPU。" : "API and GPU users start with the catalog or marketplace. Resource operators connect endpoints and GPUs in admin."}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {[
                ["API", language === "zh" ? "调用已发布模型" : "Call published models"],
                ["GPU", language === "zh" ? "租用并管理实例" : "Rent and manage instances"],
                ["OPS", language === "zh" ? "接入资源并运营" : "Connect and operate resources"],
              ].map(([label, value]) => <div className="flex items-center justify-between border-t border-background/15 pt-3 text-sm" key={label}><span className="font-mono text-accent">{label}</span><span className="text-background/75">{value}</span></div>)}
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="guides" className="section scroll-mt-20 border-y border-border bg-card">
        <div className="container">
          <div className="section-head">
            <div><p className="eyebrow">{language === "zh" ? "分步指南" : "HOW-TO GUIDES"}</p><h2>{language === "zh" ? "按你的任务查步骤。" : "Find the steps for your task."}</h2></div>
            <p>{language === "zh" ? "筛选主题或搜索关键词。每张指南都给出入口、关键步骤和必须保留的验收边界。" : "Filter by topic or search by keyword. Each guide includes an entry point, key steps, and required acceptance boundaries."}</p>
          </div>

          <div className="mb-7 grid gap-3 lg:grid-cols-[minmax(260px,1fr)_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-10" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={language === "zh" ? "搜索 API Key、SSH、vLLM…" : "Search API key, SSH, vLLM…"} aria-label={language === "zh" ? "搜索使用指南" : "Search guides"} />
            </div>
            <div className="flex flex-wrap gap-2" role="group" aria-label={language === "zh" ? "指南分类" : "Guide categories"}>
              {categories.map((item) => <Button key={item.id} variant={category === item.id ? "default" : "outline"} onClick={() => setCategory(item.id)} aria-pressed={category === item.id}>{text(item.label)}</Button>)}
            </div>
          </div>

          {filteredGuides.length > 0 ? (
            <div className="grid min-w-0 gap-5 lg:grid-cols-2">
              {filteredGuides.map((guide) => {
                const Icon = guide.icon;
                return (
                  <Card className="flex min-h-full min-w-0 flex-col overflow-hidden" id={guide.id} key={guide.id}>
                    <CardHeader className="flex-row items-center justify-between">
                      <div className="grid size-11 place-items-center rounded-lg bg-muted"><Icon className="size-5" /></div>
                      <Badge variant="outline">{text(categories.find((item) => item.id === guide.category)?.label ?? categories[0].label)}</Badge>
                    </CardHeader>
                    <CardContent className="flex min-w-0 flex-1 flex-col pt-2">
                      <CardTitle className="text-xl">{text(guide.title)}</CardTitle>
                      <CardDescription className="mt-3">{text(guide.description)}</CardDescription>
                      <ol className="my-6 grid gap-3">
                        {guide.steps.map((step, index) => <li className="flex gap-3 text-sm leading-6" key={text(step)}><span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-muted text-[10px] font-bold">{index + 1}</span><span>{text(step)}</span></li>)}
                      </ol>
                      {guide.code && (
                        <div className="relative mb-5 overflow-hidden rounded-lg border border-border bg-foreground text-background">
                          <Button className="absolute right-2 top-2 text-background hover:bg-background/10 hover:text-background" variant="ghost" size="sm" onClick={() => void copyCode(guide.id, guide.code ?? "")}>
                            {copied === guide.id ? <ClipboardCheck /> : <Clipboard />}{copied === guide.id ? (language === "zh" ? "已复制" : "Copied") : (language === "zh" ? "复制" : "Copy")}
                          </Button>
                          <pre className="overflow-x-auto p-4 pt-14 text-xs leading-6"><code>{guide.code}</code></pre>
                        </div>
                      )}
                      <Button className="mt-auto self-start" asChild variant="outline"><Link href={guide.href}>{text(guide.action)}<ArrowRight /></Link></Button>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <Card className="py-16 text-center"><Search className="mx-auto mb-4 size-7 text-muted-foreground" /><CardTitle>{language === "zh" ? "没有匹配的指南" : "No matching guides"}</CardTitle><CardDescription className="mt-2">{language === "zh" ? "换一个关键词，或切回“全部”。" : "Try another keyword or switch back to All."}</CardDescription></Card>
          )}
        </div>
      </section>

      <section id="about" className="section scroll-mt-20">
        <div className="container">
          <div className="section-head">
            <div><p className="eyebrow">{language === "zh" ? "关于与边界" : "ABOUT & BOUNDARIES"}</p><h2>{language === "zh" ? "这是平台软件，不是硬件一体机。" : "Platform software, not a hardware appliance."}</h2></div>
            <p>{language === "zh" ? "Open Compute System 部署在资源方环境中，连接 GPU、模型端点、统一网关、计量计费、实例交付和运营后台。" : "Open Compute System runs in the resource owner's environment and connects GPUs, model endpoints, a unified gateway, billing, instance delivery, and operations."}</p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            <Card><CardHeader><CheckCircle2 className="size-6 text-success" /><CardTitle className="mt-4">{language === "zh" ? "当前已实现" : "Implemented"}</CardTitle></CardHeader><CardContent><CardDescription>{language === "zh" ? "模型目录、推理副本、API Key、Token 用量、GPU 实例、余额、审计和 OpenAPI 契约。" : "Model catalog, inference replicas, API keys, token usage, GPU instances, balances, audit, and an OpenAPI contract."}</CardDescription></CardContent></Card>
            <Card><CardHeader><ShieldCheck className="size-6 text-info" /><CardTitle className="mt-4">{language === "zh" ? "明确不做" : "Out of scope"}</CardTitle></CardHeader><CardContent><CardDescription>{language === "zh" ? "硬件销售、开放供应商市场、拼租、裸金属询价、完整 CRM 和自研底层调度器。" : "Hardware sales, an open provider marketplace, shared rentals, bare-metal quoting, a full CRM, and a custom low-level scheduler."}</CardDescription></CardContent></Card>
            <Card><CardHeader><LifeBuoy className="size-6 text-warning" /><CardTitle className="mt-4">{language === "zh" ? "仍需外部验收" : "External acceptance required"}</CardTitle></CardHeader><CardContent><CardDescription>{language === "zh" ? "真实 GPU、自动模型部署、生产限流、支付、短信、实名、正式法律文本和生产部署。" : "Real GPUs, automated model deployment, production rate limiting, payments, SMS, identity checks, final legal text, and production deployment."}</CardDescription></CardContent></Card>
          </div>
        </div>
      </section>

      <section id="faq" className="section border-t border-border bg-muted/35 scroll-mt-20">
        <div className="container max-w-4xl">
          <div className="mb-8"><p className="eyebrow">FAQ</p><h2 className="text-3xl font-bold tracking-tight md:text-4xl">{language === "zh" ? "常见问题" : "Frequently asked questions"}</h2></div>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            {faqs.map(([question, answer], index) => (
              <div key={text(question)}>
                {index > 0 && <Separator />}
                <details className="group px-5 py-1">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-semibold marker:hidden">
                    {text(question)}<ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                  </summary>
                  <p className="max-w-3xl pb-5 text-sm leading-7 text-muted-foreground">{text(answer)}</p>
                </details>
              </div>
            ))}
          </div>
          <Card className="mt-6 flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div><CardTitle>{language === "zh" ? "仍然没有找到答案？" : "Still need an answer?"}</CardTitle><CardDescription className="mt-2">{language === "zh" ? "先在控制台确认状态与请求 ID，再联系部署方运维。" : "Check status and request ID in the console, then contact your deployment operator."}</CardDescription></div>
            <Button asChild variant="accent"><Link href="/console">{language === "zh" ? "打开控制台" : "Open console"}<ArrowRight /></Link></Button>
          </Card>
        </div>
      </section>
    </SiteShell>
  );
}
