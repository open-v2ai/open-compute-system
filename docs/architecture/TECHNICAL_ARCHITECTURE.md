# Open Compute System 技术方案

> GPU 实例控制面（SKU、订单、库存、实例、Outbox、Provider）仍以本文为准。现行产品已经扩展为 AI 推理商业化基础设施，模型 API、API Key、Token 计量和推理端点属于主路径；产品定位、边界与路线以 [产品 PRD](../business/PRODUCT_PRD.md) 为准。

> 文档版本：V1.0  
> 日期：2026-08-24  
> 核心技术栈：Next.js + FastAPI + PostgreSQL  
> 关联文档：[现行产品 PRD](../business/PRODUCT_PRD.md)、[历史算力供应平台 PRD](../business/GPUHOME_PARITY_PRD.md)、[历史运营管理后台 PRD](../business/ADMIN_CONSOLE_PRD.md)

---

## 1. 方案结论

本项目采用“Next.js 前端 + FastAPI 控制面 + PostgreSQL 业务主库 + Redis/Celery 异步任务 + 推理网关 + Resource/Inference Adapter”的模块化单体架构。

首期不拆微服务，不自研 Kubernetes 或 GPU 底层调度，不建设供应商工作台。平台优先跑通两个共享资源、用户、余额与审计的闭环：

```text
商品上架
-> 用户注册登录
-> 提交订单
-> 预占库存
-> 创建 GPU 实例任务
-> 获取 SSH/JupyterLab 连接信息
-> 开机/关机
-> 释放实例
-> 恢复库存
-> 后台查看订单、实例、任务和审计记录

模型/推理端点登记
-> 健康与兼容性检查
-> 设置输入/输出 Token 成本和售价
-> 发布 OpenAI 兼容模型 API
-> 用户创建 API Key
-> 鉴权、限流和健康副本路由
-> 推理运行时返回结果与 Token 用量
-> 幂等结算、余额扣减和用量记录
-> 后台查看延迟、错误、收入、成本和毛利
```

当前代码已经具备 OpenAI-compatible 推理网关、模型/副本运营和 Docker vLLM 节点 Agent。下一阶段是在真实 NVIDIA GPU 主机上验证模型下载、容器启动、健康、Token 对账和停止回收。在线支付、复杂财务、多资源路由、团队子账号和多节点推理不默认纳入首个真实试点。

已确认首期部署方式：系统完全私有部署；推理运行时使用 vLLM；客户 GPU 节点运行受控 Agent，通过 Docker 单机启动模型容器。控制面不通过 SSH 执行任意命令。Kubernetes/KServe/NIM Operator 属于后续 Adapter，不改变控制面订单、Key、Token 和审计模型。节点 Agent 详细边界见 [Docker vLLM 节点 Agent](./VLLM_NODE_AGENT.md)。

---

## 2. 架构目标与原则

### 2.1 架构目标

1. 在 8 周内完成可展示、可获客、可管理、可接入一个真实算力渠道的 MVP；
2. 将用户请求与 GPU 长任务解耦，避免实例创建占用 HTTP 请求；
3. 保证订单、库存、实例和任务状态可追踪、可重试、可人工兜底；
4. 为后续真实支付、精确计费和多资源来源预留数据与接口边界；
5. 保持工程结构简单，让小团队可以开发、部署和排障。

### 2.2 设计原则

- PostgreSQL 是订单、库存、实例、资金和任务状态的唯一业务事实来源；
- Redis 只用于缓存、频控和任务传递，不作为库存或资金账本；
- Next.js 不承载算力交付、计费和资金等核心业务逻辑；
- FastAPI 请求只创建任务并返回任务 ID，不等待底层资源交付完成；
- 所有外部写操作均携带平台业务单号和幂等键；
- 所有实例生命周期操作都生成可查询的任务记录；
- 合作方 API 失败必须如实进入失败或待人工处理状态；
- 高风险后台操作必须校验服务端权限并写入审计日志；
- 首期使用模块化单体，达到明确拆分条件后再提取独立服务。

---

## 3. 总体架构

```text
                         用户浏览器
                    ┌────────┴────────┐
                    │                 │
             官网/用户控制台      运营管理后台
                    │                 │
                    └────────┬────────┘
                             │ HTTPS
                  ┌──────────▼──────────┐
                  │ Nginx / 反向代理    │
                  │ 页面请求 -> Next.js │
                  │ /api/*   -> FastAPI │
                  └──────┬────────┬─────┘
                         │        │
               ┌─────────▼──┐  ┌──▼────────────┐
               │ Next.js    │  │ FastAPI API   │
               │ SSR / UI   │  │ 业务/权限/事务│
               └────────────┘  └──┬─────────┬──┘
                                  │         │ Outbox
                         ┌────────▼──┐   ┌──▼───────────┐
                         │PostgreSQL │   │ Redis/Celery │
                         │业务真实状态│   │ 异步任务队列 │
                         └───────────┘   └──┬───────────┘
                                            │
                                  ┌─────────▼────────┐
                                  │ Celery Worker    │
                                  │ 调度/轮询/补偿   │
                                  └─────────┬────────┘
                                            │
                                  ┌─────────▼────────┐
                                  │ ResourceProvider │
                                  ├──────────────────┤
                                  │ Mock Provider    │
                                  │ 合作方 API       │
                                  │ Kubernetes 后续  │
                                  └──────────────────┘
```

### 3.1 组件职责

| 组件 | 职责 | 不负责 |
|---|---|---|
| Next.js | 官网、算力市场、用户控制台、运营后台、SSR、交互 | 资金事务、库存锁定、GPU 长任务 |
| FastAPI | 认证、权限、商品、订单、库存、实例、任务、审计、API | 等待实例创建完成、直接运行 GPU 工作负载 |
| PostgreSQL | 业务状态、事务、幂等、审计、Outbox | 高频临时缓存 |
| Redis | 验证码频控、查询缓存、Celery Broker/Result Backend | 资金和库存最终状态 |
| Celery Worker | 库存同步、实例交付、开关机、释放、轮询、重试和补偿 | 对外暴露用户 API |
| Provider Adapter | 屏蔽不同合作方或 Kubernetes 接口差异 | 订单、余额和用户权限判断 |
| 对象存储 | 导出文件、协议附件、发票和后续镜像文件 | 保存可直接回显的明文凭据 |

---

## 4. 技术选型

### 4.1 Web

| 类别 | 选择 |
|---|---|
| 框架 | Next.js App Router、React、TypeScript |
| 样式 | Tailwind CSS |
| 官网/控制台组件 | shadcn/ui、Radix UI、Lucide |
| 管理后台组件 | Ant Design / ProComponents，按后台表格复杂度引入 |
| 服务端数据 | Server Components 直接调用 FastAPI 内网地址 |
| 客户端数据 | TanStack Query |
| 表单 | React Hook Form + Zod |
| API 客户端 | 由 FastAPI OpenAPI 自动生成 TypeScript 类型和请求层 |
| 图表 | Recharts |
| 测试 | Vitest + Playwright |

Next.js 只保留少量框架相关 Route Handler，例如健康探针、内容重验证或必要的同源回调。商品、订单、实例和后台管理等业务接口统一由 FastAPI 提供。

### 4.2 API 与 Worker

| 类别 | 选择 |
|---|---|
| Web 框架 | FastAPI |
| 数据校验 | Pydantic |
| ORM | SQLAlchemy 2.x Async |
| PostgreSQL 驱动 | asyncpg |
| 数据迁移 | Alembic |
| HTTP 客户端 | httpx |
| 队列 | Celery + Redis |
| 配置 | pydantic-settings |
| 日志 | structlog 或标准 JSON logging |
| 测试 | pytest + pytest-asyncio |
| 代码质量 | Ruff + Pyright |
| 包管理 | uv |

FastAPI 内置 `BackgroundTasks` 只用于不要求持久化的小任务。GPU 实例创建、库存同步和状态轮询必须进入 Celery；任务业务状态仍需同步写入 PostgreSQL，不能只读取 Celery Result Backend。

### 4.3 基础设施

| 类别 | 选择 |
|---|---|
| 主数据库 | PostgreSQL |
| 缓存/任务 Broker | Redis |
| 对象存储 | 本地 MinIO；生产使用阿里云 OSS 或腾讯云 COS |
| 反向代理 | Nginx |
| 容器化 | Docker + Docker Compose |
| CI/CD | GitLab CI |
| 监控 | OpenTelemetry + Prometheus/Grafana，MVP 可先落基础指标 |
| 错误跟踪 | Sentry 或同类服务，可按部署环境启用 |

所有依赖使用锁文件固定版本，不在生产构建中直接安装 `latest`。

---

## 5. 项目目录设计

目录总体沿用 Unicone Cloud 的根级 `api / web / deploy / docs` 结构、Makefile 入口、本地依赖脚本与正式 Compose 分离方式。

与参考项目不同，本项目从一开始只保留 `api/app/` 一个 Python 业务包，避免同时出现 `api/core` 与 `api/app/core` 等重复目录；另外增加 `providers`、`workers`、`repositories` 和 `outbox` 等算力平台所需边界。

```text
open-compute-system/
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   ├── logging.py
│   │   │   ├── security.py
│   │   │   └── telemetry.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── transaction.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── market.py
│   │   │   ├── orders.py
│   │   │   ├── instances.py
│   │   │   ├── tasks.py
│   │   │   ├── leads.py
│   │   │   └── admin/
│   │   ├── services/
│   │   │   ├── auth/
│   │   │   ├── catalog/
│   │   │   ├── inventory/
│   │   │   ├── orders/
│   │   │   ├── wallet/
│   │   │   ├── instances/
│   │   │   ├── leads/
│   │   │   ├── audit/
│   │   │   └── outbox/
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── partner.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── inventory_tasks.py
│   │   │   ├── instance_tasks.py
│   │   │   └── outbox_tasks.py
│   │   └── dependencies/
│   ├── migrations/
│   │   └── versions/
│   ├── scripts/
│   │   └── local/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── contract/
│   │   └── fixtures/
│   ├── .env.example
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── uv.lock
│
├── web/
│   ├── app/
│   │   ├── (site)/
│   │   │   ├── page.tsx
│   │   │   ├── market/
│   │   │   ├── solutions/
│   │   │   └── about/
│   │   ├── (console)/
│   │   │   └── console/
│   │   │       ├── page.tsx
│   │   │       ├── instances/
│   │   │       ├── orders/
│   │   │       └── profile/
│   │   └── (admin)/
│   │       └── admin/
│   │           ├── page.tsx
│   │           ├── resources/
│   │           ├── catalog/
│   │           ├── instances/
│   │           ├── users/
│   │           ├── orders/
│   │           ├── leads/
│   │           └── audit/
│   ├── components/
│   │   ├── site/
│   │   ├── console/
│   │   ├── admin/
│   │   └── ui/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   └── generated/
│   │   ├── auth/
│   │   ├── format/
│   │   └── utils.ts
│   ├── public/
│   ├── tests/
│   ├── .env.example
│   ├── Dockerfile
│   ├── package.json
│   ├── pnpm-lock.yaml
│   └── tsconfig.json
│
├── deploy/
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── default.conf
│   ├── compose.yaml
│   └── .env.example
│
├── docs/
│   ├── architecture/
│   │   └── TECHNICAL_ARCHITECTURE.md
│   ├── business/
│   │   ├── ADMIN_CONSOLE_PRD.md
│   │   ├── GPUHOME_PARITY_PRD.md
│   │   └── PROJECT_QUOTATION_BRIEF.md
│   └── setup/
│       ├── MVP_ACCEPTANCE.md
│       └── QA_REPORT.md
│
├── Makefile
└── README.md
```

### 5.1 Web 合并策略

参考 Unicone Cloud，首期官网、用户控制台和运营后台放在同一个 Next.js 应用中，使用 Route Group 隔离布局和样式：

- `(site)`：公开官网与算力市场；
- `(console)`：登录后的用户控制台；
- `(admin)`：内部运营后台。

代码合并不等于访问边界合并。生产环境可由 Nginx 将后台绑定到独立域名，并禁止公共域名访问 `/admin`；FastAPI 仍在服务端对每个后台接口执行权限校验。

达到以下任一条件后，可将后台拆成独立 Next.js 应用：

- 后台需要独立发布周期；
- 后台只能通过 VPN 或办公网络访问；
- 后台依赖明显增加并影响公开站构建；
- 前台与后台由不同团队维护。

---

## 6. FastAPI 分层约定

请求调用方向固定为：

```text
routers
-> services
-> repositories
-> SQLAlchemy models / Provider clients
```

### 6.1 各层职责

| 层 | 职责 |
|---|---|
| routers | HTTP 参数、鉴权依赖、Schema 校验、状态码和错误映射 |
| services | 业务规则、事务边界、状态机、幂等和权限策略 |
| repositories | SQL 查询、行锁、分页、持久化，不包含业务判断 |
| models | SQLAlchemy 表结构与关系 |
| schemas | Pydantic 请求、响应与内部数据结构 |
| providers | 合作方 API、Kubernetes 或本地 Agent 的适配实现 |
| workers | 异步任务入口，只编排 Service，不复制业务逻辑 |

禁止事项：

- Router 直接拼复杂 SQL；
- Worker 直接修改余额或实例状态而绕过 Service；
- Provider 判断用户权限或订单金额；
- Model 中发起外部 HTTP 请求；
- 前端根据按钮是否显示来代替服务端鉴权。

---

## 7. API 设计

统一前缀为 `/api/v1`。

### 7.1 用户端 API

```text
/api/v1/auth/*
/api/v1/users/me/*
/api/v1/market/skus
/api/v1/orders/*
/api/v1/instances/*
/api/v1/tasks/*
/api/v1/wallet/*
/api/v1/leads/*
/api/v1/notifications/*
```

### 7.2 后台 API

```text
/api/v1/admin/dashboard/*
/api/v1/admin/providers/*
/api/v1/admin/resources/*
/api/v1/admin/skus/*
/api/v1/admin/inventory/*
/api/v1/admin/instances/*
/api/v1/admin/tasks/*
/api/v1/admin/users/*
/api/v1/admin/orders/*
/api/v1/admin/leads/*
/api/v1/admin/audit-logs/*
```

### 7.3 接口约定

- 所有写接口接受或生成 `X-Request-ID`；
- 创建实例、订单、退款和支付回调接受 `Idempotency-Key`；
- 错误响应包含稳定错误码，不让前端依赖中文错误文案；
- 列表统一使用游标或页码分页，禁止默认返回全量；
- 普通创建实例请求在数据库提交后返回 `202 Accepted`；
- 返回 `task_id`，前端通过任务接口获取进度；
- MVP 首期使用 2～3 秒轮询；任务量上升后再启用 SSE；
- FastAPI OpenAPI 是前后端接口契约的单一来源；
- CI 检查 OpenAPI 生成客户端是否存在未提交差异。

示例：

```http
POST /api/v1/instances
Idempotency-Key: 9a13d15c-...
```

```json
{
  "instance_id": "ins_01...",
  "task_id": "task_01...",
  "status": "pending"
}
```

---

## 8. 核心数据模型

### 8.1 账号与权限

```text
users
user_sessions
verification_codes
admin_users
roles
permissions
admin_user_roles
role_permissions
```

### 8.2 资源与商品

```text
resource_providers
regions
resource_nodes
gpu_devices
skus
price_versions
inventory_snapshots
inventory_reservations
images
```

### 8.3 订单、资金与实例

```text
orders
wallets
ledger_entries
instances
instance_tasks
instance_credentials
port_mappings
```

### 8.4 运营与基础设施

```text
leads
notifications
audit_logs
idempotency_keys
outbox_events
```

### 8.5 数据约束

- 主键优先使用 UUIDv7 或 ULID，外部展示添加业务前缀；
- 金额使用 `BIGINT` 保存最小货币单位，禁止使用浮点数；
- 时间使用 PostgreSQL `TIMESTAMPTZ` 并统一写入 UTC；
- 价格使用版本表，不覆盖历史价格；
- 资金流水只追加，不修改和删除历史记录；
- `provider_resource_id` 在同一资源来源下唯一；
- 业务幂等键建立唯一索引；
- 凭据表只保存密文或密钥管理系统引用；
- 后台可并发修改的对象增加 `version` 字段实现乐观锁；
- 审计日志与业务数据使用同一事务写入，必要时再异步归档。

---

## 9. 实例状态机与异步任务

### 9.1 实例状态

```text
pending
-> provisioning
-> running
-> stopping
-> stopped
-> starting
-> releasing
-> released

任意执行状态
-> failed
```

实例状态描述用户资源的业务状态；Celery 的 `PENDING/STARTED/SUCCESS/FAILURE` 不得直接作为实例状态。

### 9.2 任务状态

```text
queued
-> running
-> succeeded

queued/running
-> retry_wait
-> running

queued/running/retry_wait
-> failed
-> manual_review
```

每次创建、启动、停止和释放均创建独立 `instance_tasks` 记录，字段至少包含：

- 任务 ID；
- 实例 ID；
- 操作类型；
- 幂等键；
- 当前状态和进度；
- Provider 任务 ID；
- 重试次数和下次重试时间；
- 稳定错误码和脱敏错误摘要；
- 开始、完成时间；
- 操作人或触发来源。

### 9.3 创建实例流程

```text
1. FastAPI 校验用户、SKU、库存和账户状态
2. 开启 PostgreSQL 事务
3. 使用条件更新或行锁预占库存
4. 创建订单、Instance、InstanceTask
5. 写入 OutboxEvent
6. 提交事务并返回 instance_id / task_id
7. Outbox Dispatcher 将事件投递到 Celery
8. Worker 调用 Provider.create_instance
9. Worker 轮询 Provider 任务状态
10. 成功后写入连接信息并将实例置为 running
11. 失败时按规则重试、释放预占或进入人工处理
```

### 9.4 为什么需要 Outbox

如果 FastAPI 先提交数据库、再直接发布 Celery，中间进程崩溃会产生“数据库有任务，但队列没有任务”的状态；如果先发布队列再提交数据库，则 Worker 可能读取不到尚未提交的数据。

因此订单、实例任务和 OutboxEvent 在同一数据库事务内创建。Dispatcher 使用 `FOR UPDATE SKIP LOCKED` 批量领取未发布事件，成功投递后标记发布时间。即使重复投递，Worker 也必须通过业务幂等键得到相同最终结果。

---

## 10. 算力 Provider 适配层

### 10.1 统一接口

```python
class ResourceProvider(Protocol):
    async def health_check(self) -> ProviderHealth: ...
    async def sync_inventory(self) -> list[InventoryItem]: ...
    async def create_instance(self, request: CreateRequest) -> ProviderTask: ...
    async def get_instance(self, provider_id: str) -> ProviderInstance: ...
    async def start_instance(self, provider_id: str) -> ProviderTask: ...
    async def stop_instance(self, provider_id: str) -> ProviderTask: ...
    async def release_instance(self, provider_id: str) -> ProviderTask: ...
    async def get_connection_info(self, provider_id: str) -> ConnectionInfo: ...
```

### 10.2 首期实现

1. `MockProvider`：本地开发、产品演示、自动化测试；
2. `PartnerProvider`：首个现成算力 API；
3. `KubernetesProvider`：仅预留接口，首期不实现。

### 10.3 Provider 约束

- 对外错误转换为平台稳定错误码；
- 日志不得打印合作方密钥和完整连接密码；
- 所有请求配置连接、读取和总超时；
- 查询类请求可重试，创建类请求必须结合供应方幂等能力；
- 若供应方没有幂等接口，平台必须保存请求指纹并在重试前查询真实状态；
- Provider 返回的原始状态必须映射为平台状态，不能直接透传给前端；
- 合作方库存只用于同步，用户创建前仍需在平台数据库内强校验。

---

## 11. 认证、权限与安全

### 11.1 用户认证

- 注册和登录由 FastAPI 统一实现，请求必须在手机号和邮箱中二选一；
- 用户可同时绑定手机号和邮箱，两者分别规范化并保持全局唯一，解绑后至少保留一种登录方式；
- Session、订单、实例、钱包、API Key 和用量等业务归属统一使用不可变的 `users.id`，不使用可解绑的手机号或邮箱作为关联键；
- 浏览器使用 `HttpOnly + Secure + SameSite` Cookie；
- 不在 `localStorage` 保存长期访问 Token；
- 当前绑定和解绑使用当前密码二次确认；生产接入短信与邮件供应商后，新登录方式必须先完成验证码所有权验证；
- 验证码只在 Redis 中保存摘要，并按目标地址和 IP 双重限流；生产环境禁止固定验证码模式启动。

### 11.2 管理后台

- 管理员账号与普通用户权限域分离；
- 强制 MFA；
- RBAC、数据范围和敏感字段权限均在 FastAPI 执行；
- 后台使用独立域名，生产环境可增加 VPN、IP 白名单或零信任访问；
- 资金、凭据、实名和导出操作支持二次认证；
- 临时权限必须设置过期时间。

### 11.3 凭据与密钥

- 合作方 API 密钥通过环境变量或密钥管理服务注入；
- 数据库只保存密钥引用或加密密文；
- SSH 密码和私钥默认不进入普通应用日志；
- 后台查看连接凭据时记录操作者、实例、时间、IP 和结果；
- `.env`、生产备份和对象存储数据目录不得提交到仓库。

---

## 12. 前后端集成

### 12.1 请求路由

推荐通过 Nginx 保持同源：

```text
https://example.com/*        -> Next.js
https://example.com/api/*    -> FastAPI
https://admin.example.com/*  -> Next.js /admin 路由
```

Next.js Server Components 使用内网地址访问 FastAPI，例如 `http://api:8000`；浏览器统一使用 `/api/v1`，减少 CORS 与 Cookie 配置复杂度。

### 12.2 OpenAPI 客户端

1. FastAPI 输出 `openapi.json`；
2. 脚本生成 `web/lib/api/generated/`；
3. 前端在生成类型外封装少量鉴权、错误码和 request ID 逻辑；
4. 禁止手写一套重复的 TypeScript DTO；
5. 生成目录可提交仓库，并由 CI 检查是否与后端一致。

### 12.3 状态更新

MVP 默认使用轮询：

- 实例任务页处于可见状态时每 2～3 秒查询；
- 成功、失败、人工处理后停止轮询；
- 页面隐藏时降低频率或暂停；
- 后续需要更强实时性时增加 SSE，不将 WebSocket 作为首期依赖。

---

## 13. 配置与环境

参考 Unicone Cloud，将本地开发配置和正式 Compose 配置严格分开。

### 13.1 本地开发

- `api/.env`：API 本地配置，依赖主机通常为 `127.0.0.1`；
- `web/.env.local`：Next.js 本地配置；
- PostgreSQL、Redis、MinIO 使用 `api/scripts/local/` 单容器脚本启动；
- FastAPI 和 Next.js 在宿主机运行，便于热更新和调试。

### 13.2 正式部署

- `deploy/.env`：仅供 Docker Compose 使用，主机名为 `postgres`、`redis` 等服务名；
- `deploy/.env` 不得被本地 `make dev-*` 自动加载；
- 仓库只提交 `.env.example`；
- 应用启动时校验生产必要配置，不允许使用弱默认密码或调试验证码。

### 13.3 Makefile 目标

```text
make deps            启动本地 PostgreSQL/Redis/MinIO
make dev-api         启动 FastAPI
make dev-worker      启动 Celery Worker
make dev-scheduler   启动 Celery Beat/Outbox Dispatcher
make dev-web         启动 Next.js
make test-api        运行 API 测试
make check-api       运行 Ruff/Pyright
make check-web       运行 ESLint/TypeScript
make build-all       构建 API/Web 镜像
make start           启动正式 Compose
make stop            停止正式 Compose
```

---

## 14. 部署拓扑

### 14.1 MVP 生产环境

```text
Nginx
├── Next.js Web × 1
└── FastAPI × 2

Celery Worker × 1～N
Celery Beat / Outbox Dispatcher × 1
PostgreSQL
Redis
OSS/COS
```

MVP 可以使用一台或两台云主机部署应用容器，但 PostgreSQL 必须配置定期备份。正式承载真实资金后，优先升级为托管 PostgreSQL 和托管 Redis。

### 14.2 Compose 服务

```text
web
api
worker
scheduler
nginx
postgres
redis
minio（本地或私有化时）
```

### 14.3 健康检查

- `/health/live`：进程存活，不访问外部依赖；
- `/health/ready`：PostgreSQL、Redis 和必要配置可用；
- `/health/providers`：合作方 API 健康状态，仅供内部监控；
- Worker 单独上报心跳、队列积压和最后消费时间；
- 底层 Provider 故障不应让用户无法查看已有订单和任务记录。

---

## 15. 可观测性

所有日志使用结构化 JSON，并至少关联：

```text
request_id
user_id
admin_user_id
order_id
instance_id
task_id
provider_id
provider_task_id
```

MVP 必须具备以下指标：

- API 请求量、错误率和 P95 延迟；
- 登录和验证码成功率；
- 各 SKU 当前库存与预占数量；
- Celery 队列长度、重试、失败和任务耗时；
- 实例创建、开机、关机和释放成功率；
- Provider API 成功率、错误码和延迟；
- 数据库连接池使用量；
- Outbox 未发布事件数量和最老事件等待时间。

任何日志和监控标签都不得包含密码、验证码、私钥、身份证号或支付密钥。

---

## 16. 测试策略

### 16.1 API

- Service 单元测试：状态机、金额、幂等、补偿规则；
- Repository 集成测试：真实 PostgreSQL、行锁和唯一约束；
- API 集成测试：鉴权、权限、错误码和分页；
- Provider 契约测试：Mock 与真实 Provider 满足同一接口；
- Alembic 测试：空库升级到 head，并验证现有数据库升级路径；
- Worker 测试：重复投递、超时、重试和人工处理。

### 16.2 Web

- 组件与格式化逻辑单元测试；
- API 错误码映射测试；
- Playwright 覆盖注册、登录、下单、创建实例、查看任务和释放实例；
- 运营后台验证角色权限与敏感字段脱敏；
- 桌面端和移动端分别完成真实浏览器验收。

### 16.3 上线前真实链路

自动测试通过后，还必须使用真实算力沙箱或小额资源完成：

```text
库存同步
-> 创建实例
-> 返回连接信息
-> SSH/JupyterLab 实际访问
-> 停止
-> 启动
-> 释放
-> 核对合作方与平台最终状态
```

HTTP 200 或数据库记录成功不能替代真实 GPU 交付验收。

---

## 17. 8 周实施计划

| 周期 | 重点 | 交付 |
|---|---|---|
| 第 1 周 | 工程基础 | 目录、Docker、本地依赖、FastAPI、Next.js、Alembic、OpenAPI、MockProvider |
| 第 2 周 | 官网与市场 | 首页、市场、解决方案、关于、SKU 展示、线索表单、移动端适配 |
| 第 3 周 | 账号体系 | 手机登录、Session、用户资料、后台登录、基础 RBAC |
| 第 4 周 | 商品与订单 | SKU、价格版本、库存、预占、订单、后台商品与订单管理 |
| 第 5 周 | 实例任务 | Instance、InstanceTask、Outbox、Celery、状态轮询、异常队列 |
| 第 6 周 | 真实算力接入 | PartnerProvider、库存同步、创建/开关机/释放、连接信息 |
| 第 7 周 | 安全与运维 | 审计、限流、日志、指标、备份、错误处理和后台人工兜底 |
| 第 8 周 | 验收上线 | Playwright、真实 GPU 链路、部署、文档、培训和验收 |

### 17.1 范围保护

如果真实算力 API 未按时提供或缺少库存、创建、状态查询、开关机、释放、连接信息接口，第 6 周切换为 MockProvider + 人工交付后台，不在 8 周内临时自研底层调度系统。

---

## 18. MVP 验收标准

### 18.1 工程

- [ ] `make deps / dev-api / dev-worker / dev-web` 可在新环境按文档启动；
- [ ] FastAPI OpenAPI 可生成前端 TypeScript 客户端；
- [ ] 空 PostgreSQL 数据库可通过 Alembic 升级到 head；
- [ ] Web 和 API 可分别构建 Docker 镜像；
- [ ] 本地配置与 Compose 配置不会互相污染。

### 18.2 业务

- [ ] 后台可创建、上下架 SKU 并维护价格和展示库存；
- [ ] 用户可注册、登录、提交订单并查看实例任务；
- [ ] 重复提交相同幂等键只产生一个业务实例；
- [ ] 实例创建请求快速返回任务 ID；
- [ ] Worker 可完成创建、开机、关机和释放；
- [ ] 任务失败可重试或转人工处理；
- [ ] 释放后平台库存和合作方状态一致；
- [ ] 用户可复制 SSH/JupyterLab 连接信息；
- [ ] 后台可查看订单、实例、任务、错误和审计记录。

### 18.3 安全与可靠性

- [ ] 管理员无权 API 请求被 FastAPI 拒绝；
- [ ] 敏感字段默认脱敏；
- [ ] 日志不包含验证码、密码、私钥和完整连接凭据；
- [ ] Outbox 重复投递不会重复创建实例或扣减库存；
- [ ] PostgreSQL 备份与恢复至少演练一次；
- [ ] Provider 不可用时，已有订单和实例记录仍可查询。

---

## 19. 后续演进

### 19.1 第二阶段

- 微信/支付宝真实支付和回调；
- 双分录或更严格的不可变资金流水；
- 按量计量、日结和账单核对；
- 自定义镜像、数据盘和对象存储；
- 子账号、团队配额、发票和优惠体系；
- SSE 状态推送；
- 多个 Provider 适配器。

### 19.2 拆分服务的触发条件

满足明确负载或团队边界后，再从模块化单体中拆分：

- 计量事件量显著高于普通业务请求时，拆分 Metering/Billing；
- Provider 数量增加且发布频繁时，拆分 Provisioning Control Plane；
- 通知吞吐量影响核心队列时，拆分 Notification Worker；
- 后台大查询影响交易请求时，建设只读副本或分析库；
- 一个模块需要独立扩容、独立 SLA 或独立团队维护时，才拆分为服务。

首期不因“未来可能扩展”提前引入 Kafka、Temporal、ClickHouse、Elasticsearch 或业务 Kubernetes 集群。

---

## 20. 开工前必须确认

1. 首个算力渠道的完整 API 文档和沙箱账号；
2. 库存、创建、状态查询、开关机、释放和连接信息接口是否齐全；
3. 合作方是否支持创建请求幂等键或客户端请求号；
4. 首发区域、GPU 型号、卡数和真实库存；
5. 关机后是否释放 GPU、数据保留多久；
6. 用户端是否需要首期展示余额，余额是模拟额度还是实际资金；
7. 手机短信供应商和生产短信模板；
8. 管理后台首期角色和人员数量；
9. 生产域名、后台域名、云主机和对象存储；
10. 真实支付和精确计费是否确认排除在首期验收之外。

上述问题未确认前，可以完成工程骨架、MockProvider、官网和后台基础功能，但不能承诺真实 GPU 自动交付的最终完成时间。
