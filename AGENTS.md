# AGENTS.md

本文件适用于整个仓库。执行任务前先阅读本文件、根目录 `README.md`，以及与改动相关的 `docs/` 文档。

## 项目概览

Open Compute System 是面向 GPU 资源运营方的自托管 AI 推理商业化基础设施：统一 GPU 资源、模型 API、API Key、Token 计量计费、实例交付和运营后台。GPU 实例出租与模型 API 是两种资源收益模式；当前真实推理运行时和真实 GPU Provider 仍待外部接入。拼租、裸金属询价和线索池已从产品中撤出。

- `api/`：Python 3.12+、FastAPI、SQLAlchemy Async、Alembic、Celery。
- `agent/`：客户 GPU 节点上的受控 Docker vLLM 执行 Agent；不接受任意命令。
- `web/`：Node.js 22、pnpm 11.20、Next.js 16、React 19、TypeScript。
- `deploy/`：本地依赖与生产 Docker Compose、Nginx 配置。
- `docs/business/`：产品范围与业务规则。
- `docs/architecture/`：架构、分层、状态机和接口约定。
- `docs/setup/`：验收范围与已有 QA 证据。

不要把规划文档中的未来能力当作已经实现的功能。首期固定为完全私有部署、vLLM 和 Docker 单机 Agent；Kubernetes 后置。真实 GPU、模型自动部署、生产限流、短信、支付、实名、正式法律文本和生产部署仍属于外部验收范围。

## 开始工作

1. 先检查工作区状态和现有改动；保留所有与当前任务无关的修改和生成物。
2. 阅读目标模块及其测试，不要仅依据文件名或规划文档推断当前行为。
3. 优先做满足需求的最小改动，不顺手重构无关代码。
4. 不提交、推送、部署、执行生产迁移或修改真实外部系统，除非用户明确授权。

## 常用命令

命令默认从仓库根目录执行：

```bash
# 首次安装与本地启动
cd api && uv sync
cd api && .venv/bin/python scripts/upgrade_database.py
make dev-api

cd web && pnpm install
make dev-web

# 验证
make test-api
make check-api
make check-web
cd web && pnpm build

# 后端接口变更后重新生成前端契约
make generate-client

# 验证空库迁移
cd api && DATABASE_URL=sqlite+aiosqlite:////tmp/open-compute-system-empty.db .venv/bin/alembic upgrade head
```

本地默认使用 `api/open_compute_system.db` 和进程内 Mock Outbox Dispatcher，不要求 Redis。需要 PostgreSQL/Redis 时使用 `make deps`。生产 Compose 依赖 `deploy/.env`，不要在普通开发或验证任务中启动它。

## 后端约定

- 调用方向保持为 `routers -> services -> repositories/models/providers`。
- Router 负责 HTTP 参数、鉴权依赖、Schema 校验、状态码和错误映射；业务规则、事务、状态机、幂等和权限策略放在 Service。
- Worker 只编排 Service，不绕过业务层直接修改余额、订单或实例状态。
- Provider 只处理外部资源适配，不判断用户权限或订单金额；将外部状态和错误映射为平台稳定值。
- 所有权限必须在服务端验证，不能依赖前端隐藏按钮。
- 新增或修改数据库结构时创建 Alembic migration；不要只改 SQLAlchemy model，也不要改写已发布 migration。
- 订单、实例任务和 OutboxEvent 的一致性边界不可拆散；异步消费必须可安全重复执行。
- API 前缀为 `/api/v1`。写接口保留 request ID 语义；创建实例等关键写操作保留幂等语义。
- 不记录密钥、完整密码、Cookie、令牌或完整连接凭据。

Python 使用 Ruff 约束：100 字符行宽、Python 3.12 目标版本，导入保持排序。新增业务行为时优先补充 `api/tests/` 覆盖。

## 前端约定

- 使用 App Router；页面入口位于 `web/app/`，共享 UI 位于 `web/components/`，API 封装位于 `web/lib/`。
- 新增页面、组件以及后续视觉或交互优化，适用场景必须优先使用 shadcn/ui 组件体系和设计模式；先复用已有 shadcn/ui 组件，缺失时通过 shadcn CLI 引入到 `web/components/ui/`，不要重复手写 Button、Dialog、Dropdown、Form、Table、Tabs、Toast 等已有基础组件。
- 通用界面图标统一使用 `lucide-react`。除品牌 Logo、业务专属插画、复杂数据可视化或 Lucide 确实没有对应图标的场景外，不要混用其他图标库、Emoji、字符图标或页面内手写 SVG；图标按钮必须提供可访问名称。
- 基于 shadcn/ui 做业务封装时保留其可组合、可访问的组件结构，并使用项目统一的 Tailwind 设计 Token 与变体；不要为了局部视觉效果复制出另一套基础 UI 体系。若确需偏离 shadcn/ui 或 Lucide，必须在改动说明中写明原因。
- FastAPI OpenAPI 是前后端接口契约的单一来源。不要手工编辑 `web/lib/api/generated/openapi.json` 或 `schema.ts`，也不要另写一套重复 DTO；修改后端 Schema 后运行 `make generate-client`。
- 浏览器请求保持 `/api/v1` 同源路径与 HttpOnly Cookie 会话模型。
- 对响应和错误码做显式类型处理，不让业务逻辑依赖中文错误文案。
- 修改交互或布局时同时检查桌面端和移动端；构建通过不等于真实浏览器流程验收通过。

## 配置与数据安全

- 只提交 `.env.example`；不得提交 `.env`、`.env.local`、数据库文件、密钥或真实用户数据。
- 本地配置使用宿主机地址，生产 Compose 配置使用服务名；不要混用两套环境。
- 不以清空数据库、删除迁移、重置用户改动或替换真实 Provider 为 Mock 的方式让测试通过。
- 用户接口不得暴露供应成本、后台字段或其他敏感运营数据。

## 验证要求

按改动范围执行最小但充分的验证：

- 仅后端：相关 pytest，加 `make check-api`。
- 数据库：相关测试、Alembic 当前库升级；涉及迁移拓扑时再做空库升级。
- 仅前端：`make check-web`；影响构建、路由或服务端渲染时再运行 `cd web && pnpm build`。
- API Schema：`make generate-client` 后检查生成文件差异，并执行前后端相关检查。
- 跨端业务闭环：后端测试、前端检查，并在可用时通过真实浏览器验证目标流程。

最终说明应分别列出：改了什么、执行了哪些验证、哪些真实外部链路尚未验证。不得把 lint、测试、构建、Mock Provider 或桌面浏览器结果表述为生产部署或真实 GPU 交付成功。
