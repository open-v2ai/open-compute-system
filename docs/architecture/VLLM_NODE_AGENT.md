# Docker vLLM 节点 Agent

> 状态：首期实现基线  
> 更新日期：2026-08-26

## 1. 目标

节点 Agent 运行在客户自有 GPU 主机上，接受同一私有网络内控制面的受控请求，通过 Docker 启动和停止 vLLM 容器，并返回部署状态与内部 OpenAI-compatible endpoint。

Agent 是执行层，不负责用户、价格、API Key、Token 计费、路由策略或模型发布。上述业务规则只存在于控制面。

## 2. 首期部署拓扑

    客户私有网络

    Open Compute API / Worker
             |
             | Agent Bearer Token + HTTPS/内网
             v
    GPU Node Agent
             |
             | fixed docker argv, no shell
             v
    Docker Engine -> vLLM container -> /v1

控制面、数据库、Redis、Web、Agent 和模型运行时均部署在客户环境，不向厂商托管服务传输模型、Prompt、响应、Token 或经营数据。

## 3. 受控能力

Agent 首期只提供：

- 健康检查和 Docker/GPU 运行环境摘要；
- 创建一个 vLLM 部署；
- 查询部署和容器状态；
- 停止并删除指定部署容器；
- 返回部署内部端点；
- 对同一 deployment_id 提供幂等结果。

Agent 不提供：

- 任意 shell、脚本或 Docker 参数；
- 任意镜像、挂载路径、host network 或 privileged；
- 上传文件、读取宿主机文件或查看其他容器；
- 用户、API Key、Token 计费和模型发布；
- 自动接受未经确认的模型许可证；
- Kubernetes 调度或多节点并行。

## 4. 固定参数与校验

控制面可以提交：

- deployment_id；
- Hugging Face/本地登记模型 ID；
- 对外 served model name；
- GPU device IDs；
- tensor parallel size；
- max model length；
- 容器监听端口；
- 经过 allowlist 校验的 vLLM 镜像；
- 可选的 Hugging Face Token 环境变量引用。

Agent 自己决定：

- 容器名称前缀；
- 模型缓存宿主机根目录；
- Docker labels；
- restart policy；
- 容器内部端口；
- 固定 vLLM entrypoint 与参数顺序。

所有字符串使用严格格式校验，Docker 通过 argv 调用且 shell=False。真实密钥只来自 Agent 环境变量，不进入控制面数据库、请求正文、日志或审计摘要。

## 5. 认证与网络

- Agent 使用独立高熵 Bearer Token；
- 控制面数据库只保存 Token 对应的环境变量名；
- 生产建议使用私有网段、防火墙 allowlist 和 HTTPS/mTLS；
- Agent 默认只监听显式配置的地址，不公开到互联网；
- 健康接口也需要认证，进程级 live 接口除外；
- 日志不得记录 Authorization、HF Token、Prompt 或模型响应。

## 6. 状态映射

| Agent 状态 | 控制面部署状态 |
|---|---|
| absent | pending/stopped |
| creating | provisioning |
| running + endpoint healthy | running |
| running + endpoint unhealthy | degraded |
| exited | failed/stopped |
| removing | stopping |

HTTP 创建成功只表示 Docker 请求被接受，不等于模型已经加载。控制面必须继续轮询 Agent 和 vLLM /v1/models，健康后才能把推理副本标为 healthy 或上架模型。

## 7. Kubernetes 演进

后续增加 Kubernetes Agent/Adapter 时保持同一部署服务接口：

- create deployment；
- get deployment；
- stop deployment；
- health/capacity；
- endpoint/credential reference。

Kubernetes 实现可以使用 Deployment、Service、PVC、GPU resource limits 和 KServe/NIM Operator，但不能让 Kubernetes 对象状态直接替代控制面模型发布、Token 计费或业务审计状态。
