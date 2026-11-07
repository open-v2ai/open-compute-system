# Open Compute System Node Agent

受控 Docker vLLM 节点执行层。Agent 完全运行在客户环境，只接受创建、查询和删除平台管理的 vLLM 部署，不提供任意 shell。

## 本地开发

使用独立锁文件安装依赖并运行检查：

    uv sync --frozen
    uv run ruff check app tests
    uv run pytest -q

启动前至少配置一个 32 字符以上的 AGENT_TOKEN：

    AGENT_TOKEN=replace-with-a-long-random-token \
      uv run uvicorn app.main:app --host 127.0.0.1 --port 8110

真实节点还需要 Docker、NVIDIA Driver、NVIDIA Container Toolkit，以及具有商业使用权的模型和权重访问凭据。

生产环境不得使用示例 Token，不应把 Agent 或 vLLM 端口直接暴露到公网。Docker socket 等同宿主机高权限能力，部署时必须限制 Agent 容器、网络和操作人员权限。
