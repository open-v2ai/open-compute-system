from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.identity import normalize_email, normalize_phone


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class IdentityRequest(APIModel):
    phone: str | None = None
    email: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else None

    @model_validator(mode="after")
    def validate_exactly_one_identity(self) -> "IdentityRequest":
        if (self.phone is None) == (self.email is None):
            raise ValueError("手机号和邮箱必须且只能填写一个")
        return self


class LoginRequest(IdentityRequest):
    password: str


class AdminLoginRequest(APIModel):
    username: str
    password: str
    mfa_code: str = Field(min_length=6, max_length=6)


class RegisterRequest(IdentityRequest):
    password: str = Field(min_length=8, max_length=32)
    nickname: str = Field(default="算力用户", max_length=80)
    accepted_terms: bool

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(
            char.isdigit() for char in value
        ):
            raise ValueError("密码必须同时包含字母和数字")
        return value


class UserResponse(APIModel):
    id: str
    phone: str | None
    email: str | None
    nickname: str
    balance_cents: int
    real_name_status: str
    status: str


class BindIdentityRequest(IdentityRequest):
    current_password: str


class UnbindIdentityRequest(APIModel):
    current_password: str


class AdminResponse(APIModel):
    id: str
    username: str
    display_name: str
    role: str
    mfa_enabled: bool
    permissions: list[str]


class SKUResponse(APIModel):
    id: str
    name: str
    gpu_model: str
    gpu_memory_gb: int
    gpu_count: int
    vcpu: int
    memory_gb: int
    system_disk_gb: int
    data_disk_gb: int
    region: str
    zone: str
    cpu_vendor: str
    price_hour_cents: int
    price_day_cents: int
    price_week_cents: int
    price_month_cents: int
    inventory_available: int
    status: str
    tag: str | None
    recommended: bool
    version: int


class AdminSKUResponse(SKUResponse):
    provider_id: str | None
    cost_hour_cents: int | None
    inventory_total: int
    inventory_reserved: int


class SKUCreateRequest(APIModel):
    name: str
    gpu_model: str
    gpu_memory_gb: int = Field(gt=0)
    gpu_count: int = Field(gt=0, le=8)
    vcpu: int = Field(gt=0)
    memory_gb: int = Field(gt=0)
    region: str
    zone: str = "A 区"
    cpu_vendor: str = "Intel"
    price_hour_cents: int = Field(gt=0)
    price_day_cents: int = Field(gt=0)
    price_week_cents: int = Field(gt=0)
    price_month_cents: int = Field(gt=0)
    cost_hour_cents: int = Field(ge=0)
    inventory_total: int = Field(ge=0)
    tag: str | None = None
    recommended: bool = False


class SKUUpdateRequest(APIModel):
    version: int
    price_hour_cents: int | None = Field(default=None, gt=0)
    price_day_cents: int | None = Field(default=None, gt=0)
    price_week_cents: int | None = Field(default=None, gt=0)
    price_month_cents: int | None = Field(default=None, gt=0)
    cost_hour_cents: int | None = Field(default=None, ge=0)
    inventory_total: int | None = Field(default=None, ge=0)
    status: Literal["draft", "published", "unpublished", "archived"] | None = None
    tag: str | None = None
    recommended: bool | None = None
    reason: str = "运营调整"


class CreateInstanceRequest(APIModel):
    sku_id: str
    name: str = Field(min_length=2, max_length=80)
    image: str = "PyTorch 2.7 · CUDA 12.8"
    billing_mode: Literal["hourly", "daily", "weekly", "monthly"] = "hourly"


class TaskResponse(APIModel):
    id: str
    instance_id: str
    action: str
    status: str
    progress: int
    attempt_count: int
    retry_count: int
    error_code: str | None
    error_summary: str | None
    created_at: datetime
    completed_at: datetime | None


class InstanceResponse(APIModel):
    id: str
    name: str
    image: str
    billing_mode: str
    status: str
    provider_instance_id: str | None
    ssh_host: str | None
    ssh_port: int | None
    jupyter_url: str | None
    credential_hint: str | None
    created_at: datetime
    sku: SKUResponse


class CreateInstanceResponse(APIModel):
    instance_id: str
    task_id: str
    status: str


class OrderResponse(APIModel):
    id: str
    order_type: str
    billing_mode: str
    amount_cents: int
    status: str
    created_at: datetime
    sku: SKUResponse


class DashboardResponse(APIModel):
    users: int
    running_instances: int
    failed_tasks: int
    available_inventory: int
    orders: int
    sales_cents: int
    published_models: int
    healthy_replicas: int
    inference_requests: int
    inference_tokens: int
    inference_revenue_cents: int


class AdminInstanceResponse(APIModel):
    id: str
    name: str
    user: str
    user_id: str
    contact: str
    sku: str
    region: str
    status: str
    created_at: datetime


class AdminUserResponse(APIModel):
    id: str
    nickname: str
    phone: str | None
    email: str | None
    real_name_status: str
    balance_cents: int | None
    status: str
    created_at: datetime


class AdminOrderResponse(APIModel):
    id: str
    user: str
    user_id: str
    contact: str
    sku: str
    billing_mode: str
    amount_cents: int
    status: str
    created_at: datetime


class WalletTransactionResponse(APIModel):
    id: str
    order_id: str | None
    transaction_type: str
    amount_cents: int
    balance_after_cents: int
    description: str
    created_at: datetime


class ProviderResponse(APIModel):
    id: str
    name: str
    provider_type: str
    access_mode: str
    region: str
    health_status: str
    enabled: bool
    updated_at: datetime


class AuditResponse(APIModel):
    id: str
    actor_type: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    request_id: str | None
    summary: dict | None
    result: str
    created_at: datetime


class AutoRouterConfigResponse(APIModel):
    id: str
    virtual_model_id: str
    classifier_model_id: str
    simple_model_id: str
    complex_model_id: str
    fallback_tier: Literal["simple", "complex"]
    classifier_timeout_seconds: int
    version: int
    created_at: datetime
    updated_at: datetime


class AutoRouterConfigRequest(APIModel):
    classifier_model_id: str
    simple_model_id: str
    complex_model_id: str
    fallback_tier: Literal["simple", "complex"] = "complex"
    classifier_timeout_seconds: int = Field(default=5, ge=1, le=30)
    version: int | None = None


class InferenceModelResponse(APIModel):
    id: str
    slug: str
    display_name: str
    description: str
    context_length: int
    price_prompt_per_mtok_cents: int
    price_completion_per_mtok_cents: int
    status: str
    version: int
    is_auto_router: bool


class AdminInferenceModelResponse(InferenceModelResponse):
    cost_prompt_per_mtok_cents: int | None
    cost_completion_per_mtok_cents: int | None
    backend_type: str
    replica_count: int = 0
    router_config: AutoRouterConfigResponse | None = None


class InferenceModelCreateRequest(APIModel):
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._/-]+$")
    display_name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=500)
    context_length: int = Field(default=8192, gt=0, le=2_000_000)
    price_prompt_per_mtok_cents: int = Field(gt=0)
    price_completion_per_mtok_cents: int = Field(gt=0)
    cost_prompt_per_mtok_cents: int = Field(ge=0)
    cost_completion_per_mtok_cents: int = Field(ge=0)
    backend_type: Literal["mock", "openai_compatible", "auto_router"] = (
        "openai_compatible"
    )
    status: Literal["draft", "unpublished"] = "draft"


class InferenceModelUpdateRequest(APIModel):
    version: int
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    price_prompt_per_mtok_cents: int | None = Field(default=None, gt=0)
    price_completion_per_mtok_cents: int | None = Field(default=None, gt=0)
    cost_prompt_per_mtok_cents: int | None = Field(default=None, ge=0)
    cost_completion_per_mtok_cents: int | None = Field(default=None, ge=0)
    status: Literal["draft", "published", "unpublished", "archived"] | None = None
    reason: str = "运营调整"


class AdminInferenceReplicaResponse(APIModel):
    id: str
    model_id: str
    label: str
    endpoint: str
    upstream_model: str
    credential_env_var: str | None
    timeout_seconds: int
    capacity_tpm: int | None
    weight: int
    health_status: str
    enabled: bool
    version: int
    last_health_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InferenceReplicaCreateRequest(APIModel):
    label: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    endpoint: str = Field(min_length=8, max_length=240)
    upstream_model: str = Field(min_length=1, max_length=160)
    credential_env_var: str | None = Field(
        default=None, max_length=120, pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    timeout_seconds: int = Field(default=120, ge=1, le=1800)
    capacity_tpm: int | None = Field(default=None, gt=0)
    weight: int = Field(default=100, ge=1, le=10_000)
    enabled: bool = True


class InferenceReplicaUpdateRequest(APIModel):
    version: int
    endpoint: str | None = Field(default=None, min_length=8, max_length=240)
    upstream_model: str | None = Field(default=None, min_length=1, max_length=160)
    credential_env_var: str | None = Field(
        default=None, max_length=120, pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    timeout_seconds: int | None = Field(default=None, ge=1, le=1800)
    capacity_tpm: int | None = Field(default=None, gt=0)
    weight: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool | None = None


class InferenceNodeCreateRequest(APIModel):
    name: str = Field(min_length=2, max_length=120)
    agent_url: str = Field(min_length=8, max_length=240)
    agent_token_env_var: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    runtime_credential_env_var: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )


class InferenceNodeResponse(APIModel):
    id: str
    name: str
    agent_url: str
    agent_token_env_var: str
    runtime_credential_env_var: str | None
    enabled: bool
    status: str
    docker_version: str | None
    gpu_summary: list[dict]
    version: int
    last_health_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InferenceDeploymentCreateRequest(APIModel):
    model_id: str
    node_id: str
    model_source_id: str = Field(
        min_length=3,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]+$",
    )
    served_model_name: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._/-]+$",
    )
    image: str | None = Field(default=None, max_length=240)
    gpu_device_ids: list[int] = Field(min_length=1, max_length=8)
    tensor_parallel_size: int = Field(default=1, ge=1, le=8)
    host_port: int = Field(ge=1024, le=65535)
    max_model_len: int | None = Field(default=None, ge=256, le=2_000_000)
    gpu_memory_utilization: float = Field(default=0.9, ge=0.1, le=0.98)
    huggingface_token_env_var: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )

    @field_validator("gpu_device_ids")
    @classmethod
    def validate_deployment_gpu_ids(cls, value: list[int]) -> list[int]:
        if any(item < 0 or item > 255 for item in value):
            raise ValueError("GPU device IDs must be between 0 and 255")
        if len(set(value)) != len(value):
            raise ValueError("GPU device IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_deployment_parallelism(self) -> "InferenceDeploymentCreateRequest":
        if self.tensor_parallel_size != len(self.gpu_device_ids):
            raise ValueError("tensor_parallel_size must equal the number of GPU device IDs")
        return self


class InferenceDeploymentResponse(APIModel):
    id: str
    model_id: str
    node_id: str
    replica_id: str | None
    model_source_id: str
    served_model_name: str
    image: str | None
    gpu_device_ids: list[int]
    tensor_parallel_size: int
    host_port: int
    max_model_len: int | None
    gpu_memory_utilization: float
    huggingface_token_env_var: str | None
    status: str
    endpoint: str | None
    error_code: str | None
    error_summary: str | None
    version: int
    deployed_at: datetime | None
    stopped_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OpenAIModelCard(APIModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "opencompute"


class OpenAIModelListResponse(APIModel):
    object: str = "list"
    data: list[OpenAIModelCard]


class ChatCompletionMessage(APIModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32_000)


class ChatCompletionRequest(APIModel):
    model: str = Field(min_length=3, max_length=120)
    messages: list[ChatCompletionMessage] = Field(min_length=1, max_length=100)
    max_tokens: int = Field(default=512, ge=1, le=8192)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)


class ApiKeyCreateRequest(APIModel):
    name: str = Field(min_length=2, max_length=80)
    credit_limit_cents: int | None = Field(default=None, ge=0)
    rpm_limit: int = Field(default=60, ge=1, le=600)
    tpm_limit: int = Field(default=100_000, ge=1, le=100_000_000)
    allowed_models: list[str] = Field(default_factory=list, max_length=100)


class ApiKeyResponse(APIModel):
    id: str
    name: str
    key_prefix: str
    status: str
    credit_limit_cents: int | None
    spent_cents: int
    rpm_limit: int
    tpm_limit: int
    allowed_models: list[str]
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    secret: str


class UsageEventResponse(APIModel):
    id: str
    request_id: str
    user_id: str
    model_slug: str
    routed_model_slug: str | None
    routing_tier: str | None
    routing_decision_source: str | None
    classifier_model_slug: str | None
    classifier_latency_ms: int
    replica_label: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_micros: int
    debit_cents: int
    status: str
    api_key_id: str | None
    conversation_id: str | None
    created_at: datetime


class ConversationCreateRequest(APIModel):
    model_slug: str = Field(min_length=3, max_length=120)
    title: str = Field(default="新对话", max_length=160)


class ConversationResponse(APIModel):
    id: str
    title: str
    model_slug: str
    status: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(APIModel):
    id: str
    role: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[ChatMessageResponse]


class ConversationSendRequest(APIModel):
    content: str = Field(min_length=1, max_length=16_000)
    max_tokens: int = Field(default=512, ge=1, le=8192)


class ConversationSendResponse(APIModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
