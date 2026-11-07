# 模型 API 与 Token 商业化

模型 API 是现行产品主干之一，与 GPU 实例出租共享用户、余额、资源、订单和运营能力。当前代码已经具备商业化网关骨架，但未接真实推理引擎之前，不得当作生产模型服务对外。

## 现在有什么

- 模型目录、网页 Chat（服务端会话）、API Key、OpenAI 兼容 `/api/v1/chat/completions` 与 `/api/v1/models`
- `opencompute/auto` 虚拟模型：先用小模型判断任务复杂度，再路由到简单或复杂模型；详见 [Auto Router 设计](../architecture/AUTO_ROUTER.md)
- 与租卡共用 `User.balance_cents`；亚分用 `inference_remainder_micros`
- 推理集群与示例模型当前均为 **Mock**（`opencompute/qwen3-8b`、`opencompute/qwen3-32b`）
- 下一阶段接入客户自有 vLLM/NIM/OpenAI-compatible 端点，不转售 OpenRouter
- 首期节点 Agent 已固定为 Docker 单机 + vLLM；Kubernetes/KServe/NIM Operator 后续接入
- Agent 只接受受控模型部署参数，不提供任意 shell、任意镜像或任意挂载

## 边界

Mock 跑通不等于真实 GPU 推理交付。生产环境默认禁止 Mock 推理后端（与 MockProvider 策略一致）。

公开导航应展示模型 API；用户控制台默认展示 API Key 和 Token 用量；运营后台默认展示模型、端点和用量。

## 接入示例（仅 Mock）

```text
base_url: https://<host>/api/v1
api_key:  ocs_...
model:    opencompute/qwen3-8b
```
