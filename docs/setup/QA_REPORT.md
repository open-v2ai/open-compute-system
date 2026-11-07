# MVP 验收报告

日期：2026-08-24

> 本报告记录当时的浏览器与自动化结果。之后产品已收成控制面：线索/拼租/裸金属不再属于现行范围，产品路线以 `docs/business/PRODUCT_PRD.md` 为准，已实现与验收边界以 `README.md` 和 `MVP_ACCEPTANCE.md` 为准。

## 自动化与构建

| 项目 | 结果 |
|---|---|
| API Ruff | 通过 |
| API pytest | 13 passed |
| Web TypeScript 5.9.3 | 通过 |
| Web ESLint | 通过 |
| Web Vitest | 4 passed |
| Next.js 生产构建 | 29 个路由（含图标路由）生成成功 |
| Alembic 空库升级 | `9a8b7c6d5e4f (head)` |
| Docker Compose 配置 | 通过 |
| API Docker 镜像 | 本轮未复验（Docker registry 无法拉取基础镜像） |
| Web Docker 镜像 | 本轮未复验（Docker registry 无法拉取基础镜像） |

## 真实浏览器验收

桌面端：

- 官网首屏、导航、产品与服务模块正常；
- 市场公开展示 4 个 SKU，库存、无货和价格状态正确；
- GPU 筛选同步到 `?gpu=A100`，刷新和复制 URL 可恢复；
- 用户端接口和页面不展示供应成本；
- 用户创建实例后演示余额由 ¥5,000.00 扣为 ¥4,997.52，并生成一条 `debit` 资金流水；
- 未登录创建实例跳转登录，并保留完整 SKU 查询参数；
- 登录后创建 A100 实例，页面轮询到运行中；
- SSH 命令与 JupyterLab 地址可见；
- 关机后进入已关机，重新开机后恢复运行中；
- 后台看板展示用户、实例、库存、订单与销售额；
- 后台销售额只统计已履约订单，审计页展示关联 Request ID；
- 后台 SKU 页面展示供应成本与毛利率；
- 创建、关机、开机任务和审计记录可以关联；
- 裸金属表单提交成功，线索进入统一池并可更新跟进阶段；
- 用户、后台和移动页面控制台错误数均为 0。

移动端（390 × 844）：

- 桌面导航隐藏，抽屉导航包含完整 7 个入口；
- 首页 Hero、CTA 和 GPU 状态卡正常排列；
- 市场筛选为双列紧凑布局；
- 页面 `scrollWidth === innerWidth`，无横向溢出。

## 浏览器验收中修复的问题

1. 用户从带 SKU 的创建入口跳转登录时，查询参数曾丢失；已改为保存完整 pathname 与 search。
2. 请求封装添加 `Idempotency-Key` 时覆盖了 JSON `Content-Type`，导致页面创建实例返回 422；已修正 Header 合并顺序。
3. 加入 Origin 校验后，开发默认源使用 `localhost`，但真实入口为 `127.0.0.1`，导致合法登录返回 403；已统一本地默认源并重新完成浏览器闭环。

## 本轮 P0/P1 加固

- 订单、余额、资金流水、库存、实例任务和 Outbox 保持单事务写入；创建失败自动退款并恢复库存；
- 幂等键按 actor、operation 和请求摘要绑定；生命周期重放返回原任务；
- 任务和 Outbox 增加租约、退避、卡死恢复、人工复核和持久化后台重试；
- 生产禁止演示 Seed、默认 Session Secret、固定 MFA 和启用的 MockProvider；
- 增加双提交 CSRF、Origin、Trusted Host、登录/线索频控、CSP、安全响应头和独立后台域名；
- 后台权限由服务端 RBAC 执行，成本和余额按字段权限脱敏；
- GitLab CI 覆盖 Ruff、pytest、OpenAPI 漂移、TypeScript、ESLint、Vitest 和 Next.js 构建。

## 当前验证限制

本轮 Docker registry 无法完成 PostgreSQL 16 / Redis 7 镜像下载，因此没有执行真实 PostgreSQL、Redis、Celery 多进程集成测试；CI 已配置相同服务，不能以本地 SQLite 结果替代该项。

## 外部验收边界

真实算力、短信、支付、计量、实名、正式法律文本和生产环境尚无外部账号或配置。本报告不把 MockProvider 的 HTTP 成功等同于真实 GPU 交付；上线前必须按 `MVP_ACCEPTANCE.md` 的真实链路清单补验。
