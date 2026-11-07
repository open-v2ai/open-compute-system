// Generated from FastAPI OpenAPI. Do not edit by hand.

export interface AdminInferenceModelResponse {
  "id": string;
  "slug": string;
  "display_name": string;
  "description": string;
  "context_length": number;
  "price_prompt_per_mtok_cents": number;
  "price_completion_per_mtok_cents": number;
  "status": string;
  "version": number;
  "is_auto_router": boolean;
  "cost_prompt_per_mtok_cents": number | null;
  "cost_completion_per_mtok_cents": number | null;
  "backend_type": string;
  "replica_count"?: number;
  "router_config"?: AutoRouterConfigResponse | null;
}

export interface AdminInferenceReplicaResponse {
  "id": string;
  "model_id": string;
  "label": string;
  "endpoint": string;
  "upstream_model": string;
  "credential_env_var": string | null;
  "timeout_seconds": number;
  "capacity_tpm": number | null;
  "weight": number;
  "health_status": string;
  "enabled": boolean;
  "version": number;
  "last_health_checked_at": string | null;
  "created_at": string;
  "updated_at": string;
}

export interface AdminInstanceResponse {
  "id": string;
  "name": string;
  "user": string;
  "user_id": string;
  "contact": string;
  "sku": string;
  "region": string;
  "status": string;
  "created_at": string;
}

export interface AdminLoginRequest {
  "username": string;
  "password": string;
  "mfa_code": string;
}

export interface AdminOrderResponse {
  "id": string;
  "user": string;
  "user_id": string;
  "contact": string;
  "sku": string;
  "billing_mode": string;
  "amount_cents": number;
  "status": string;
  "created_at": string;
}

export interface AdminResponse {
  "id": string;
  "username": string;
  "display_name": string;
  "role": string;
  "mfa_enabled": boolean;
  "permissions": Array<string>;
}

export interface AdminSKUResponse {
  "id": string;
  "name": string;
  "gpu_model": string;
  "gpu_memory_gb": number;
  "gpu_count": number;
  "vcpu": number;
  "memory_gb": number;
  "system_disk_gb": number;
  "data_disk_gb": number;
  "region": string;
  "zone": string;
  "cpu_vendor": string;
  "price_hour_cents": number;
  "price_day_cents": number;
  "price_week_cents": number;
  "price_month_cents": number;
  "inventory_available": number;
  "status": string;
  "tag": string | null;
  "recommended": boolean;
  "version": number;
  "provider_id": string | null;
  "cost_hour_cents": number | null;
  "inventory_total": number;
  "inventory_reserved": number;
}

export interface AdminUserResponse {
  "id": string;
  "nickname": string;
  "phone": string | null;
  "email": string | null;
  "real_name_status": string;
  "balance_cents": number | null;
  "status": string;
  "created_at": string;
}

export interface ApiKeyCreateRequest {
  "name": string;
  "credit_limit_cents"?: number | null;
  "rpm_limit"?: number;
  "tpm_limit"?: number;
  "allowed_models"?: Array<string>;
}

export interface ApiKeyCreatedResponse {
  "id": string;
  "name": string;
  "key_prefix": string;
  "status": string;
  "credit_limit_cents": number | null;
  "spent_cents": number;
  "rpm_limit": number;
  "tpm_limit": number;
  "allowed_models": Array<string>;
  "last_used_at": string | null;
  "created_at": string;
  "secret": string;
}

export interface ApiKeyResponse {
  "id": string;
  "name": string;
  "key_prefix": string;
  "status": string;
  "credit_limit_cents": number | null;
  "spent_cents": number;
  "rpm_limit": number;
  "tpm_limit": number;
  "allowed_models": Array<string>;
  "last_used_at": string | null;
  "created_at": string;
}

export interface AuditResponse {
  "id": string;
  "actor_type": string;
  "actor_id": string;
  "action": string;
  "object_type": string;
  "object_id": string;
  "request_id": string | null;
  "summary": Record<string, unknown> | null;
  "result": string;
  "created_at": string;
}

export interface AutoRouterConfigRequest {
  "classifier_model_id": string;
  "simple_model_id": string;
  "complex_model_id": string;
  "fallback_tier"?: "simple" | "complex";
  "classifier_timeout_seconds"?: number;
  "version"?: number | null;
}

export interface AutoRouterConfigResponse {
  "id": string;
  "virtual_model_id": string;
  "classifier_model_id": string;
  "simple_model_id": string;
  "complex_model_id": string;
  "fallback_tier": "simple" | "complex";
  "classifier_timeout_seconds": number;
  "version": number;
  "created_at": string;
  "updated_at": string;
}

export interface BindIdentityRequest {
  "phone"?: string | null;
  "email"?: string | null;
  "current_password": string;
}

export interface ChatCompletionMessage {
  "role": "system" | "user" | "assistant";
  "content": string;
}

export interface ChatCompletionRequest {
  "model": string;
  "messages": Array<ChatCompletionMessage>;
  "max_tokens"?: number;
  "stream"?: boolean;
  "temperature"?: number | null;
}

export interface ChatMessageResponse {
  "id": string;
  "role": string;
  "content": string;
  "prompt_tokens": number;
  "completion_tokens": number;
  "created_at": string;
}

export interface ConversationCreateRequest {
  "model_slug": string;
  "title"?: string;
}

export interface ConversationDetailResponse {
  "id": string;
  "title": string;
  "model_slug": string;
  "status": string;
  "created_at": string;
  "updated_at": string;
  "messages": Array<ChatMessageResponse>;
}

export interface ConversationResponse {
  "id": string;
  "title": string;
  "model_slug": string;
  "status": string;
  "created_at": string;
  "updated_at": string;
}

export interface ConversationSendRequest {
  "content": string;
  "max_tokens"?: number;
}

export interface ConversationSendResponse {
  "user_message": ChatMessageResponse;
  "assistant_message": ChatMessageResponse;
}

export interface CreateInstanceRequest {
  "sku_id": string;
  "name": string;
  "image"?: string;
  "billing_mode"?: "hourly" | "daily" | "weekly" | "monthly";
}

export interface CreateInstanceResponse {
  "instance_id": string;
  "task_id": string;
  "status": string;
}

export interface DashboardResponse {
  "users": number;
  "running_instances": number;
  "failed_tasks": number;
  "available_inventory": number;
  "orders": number;
  "sales_cents": number;
  "published_models": number;
  "healthy_replicas": number;
  "inference_requests": number;
  "inference_tokens": number;
  "inference_revenue_cents": number;
}

export interface HTTPValidationError {
  "detail"?: Array<ValidationError>;
}

export interface InferenceDeploymentCreateRequest {
  "model_id": string;
  "node_id": string;
  "model_source_id": string;
  "served_model_name": string;
  "image"?: string | null;
  "gpu_device_ids": Array<number>;
  "tensor_parallel_size"?: number;
  "host_port": number;
  "max_model_len"?: number | null;
  "gpu_memory_utilization"?: number;
  "huggingface_token_env_var"?: string | null;
}

export interface InferenceDeploymentResponse {
  "id": string;
  "model_id": string;
  "node_id": string;
  "replica_id": string | null;
  "model_source_id": string;
  "served_model_name": string;
  "image": string | null;
  "gpu_device_ids": Array<number>;
  "tensor_parallel_size": number;
  "host_port": number;
  "max_model_len": number | null;
  "gpu_memory_utilization": number;
  "huggingface_token_env_var": string | null;
  "status": string;
  "endpoint": string | null;
  "error_code": string | null;
  "error_summary": string | null;
  "version": number;
  "deployed_at": string | null;
  "stopped_at": string | null;
  "created_at": string;
  "updated_at": string;
}

export interface InferenceModelCreateRequest {
  "slug": string;
  "display_name": string;
  "description"?: string;
  "context_length"?: number;
  "price_prompt_per_mtok_cents": number;
  "price_completion_per_mtok_cents": number;
  "cost_prompt_per_mtok_cents": number;
  "cost_completion_per_mtok_cents": number;
  "backend_type"?: "mock" | "openai_compatible" | "auto_router";
  "status"?: "draft" | "unpublished";
}

export interface InferenceModelResponse {
  "id": string;
  "slug": string;
  "display_name": string;
  "description": string;
  "context_length": number;
  "price_prompt_per_mtok_cents": number;
  "price_completion_per_mtok_cents": number;
  "status": string;
  "version": number;
  "is_auto_router": boolean;
}

export interface InferenceModelUpdateRequest {
  "version": number;
  "display_name"?: string | null;
  "description"?: string | null;
  "price_prompt_per_mtok_cents"?: number | null;
  "price_completion_per_mtok_cents"?: number | null;
  "cost_prompt_per_mtok_cents"?: number | null;
  "cost_completion_per_mtok_cents"?: number | null;
  "status"?: "draft" | "published" | "unpublished" | "archived" | null;
  "reason"?: string;
}

export interface InferenceNodeCreateRequest {
  "name": string;
  "agent_url": string;
  "agent_token_env_var": string;
  "runtime_credential_env_var"?: string | null;
}

export interface InferenceNodeResponse {
  "id": string;
  "name": string;
  "agent_url": string;
  "agent_token_env_var": string;
  "runtime_credential_env_var": string | null;
  "enabled": boolean;
  "status": string;
  "docker_version": string | null;
  "gpu_summary": Array<Record<string, unknown>>;
  "version": number;
  "last_health_checked_at": string | null;
  "created_at": string;
  "updated_at": string;
}

export interface InferenceReplicaCreateRequest {
  "label": string;
  "endpoint": string;
  "upstream_model": string;
  "credential_env_var"?: string | null;
  "timeout_seconds"?: number;
  "capacity_tpm"?: number | null;
  "weight"?: number;
  "enabled"?: boolean;
}

export interface InferenceReplicaUpdateRequest {
  "version": number;
  "endpoint"?: string | null;
  "upstream_model"?: string | null;
  "credential_env_var"?: string | null;
  "timeout_seconds"?: number | null;
  "capacity_tpm"?: number | null;
  "weight"?: number | null;
  "enabled"?: boolean | null;
}

export interface InstanceResponse {
  "id": string;
  "name": string;
  "image": string;
  "billing_mode": string;
  "status": string;
  "provider_instance_id": string | null;
  "ssh_host": string | null;
  "ssh_port": number | null;
  "jupyter_url": string | null;
  "credential_hint": string | null;
  "created_at": string;
  "sku": SKUResponse;
}

export interface LoginRequest {
  "phone"?: string | null;
  "email"?: string | null;
  "password": string;
}

export interface OpenAIModelCard {
  "id": string;
  "object"?: string;
  "created": number;
  "owned_by"?: string;
}

export interface OpenAIModelListResponse {
  "object"?: string;
  "data": Array<OpenAIModelCard>;
}

export interface OrderResponse {
  "id": string;
  "order_type": string;
  "billing_mode": string;
  "amount_cents": number;
  "status": string;
  "created_at": string;
  "sku": SKUResponse;
}

export interface ProviderResponse {
  "id": string;
  "name": string;
  "provider_type": string;
  "access_mode": string;
  "region": string;
  "health_status": string;
  "enabled": boolean;
  "updated_at": string;
}

export interface RegisterRequest {
  "phone"?: string | null;
  "email"?: string | null;
  "password": string;
  "nickname"?: string;
  "accepted_terms": boolean;
}

export interface SKUCreateRequest {
  "name": string;
  "gpu_model": string;
  "gpu_memory_gb": number;
  "gpu_count": number;
  "vcpu": number;
  "memory_gb": number;
  "region": string;
  "zone"?: string;
  "cpu_vendor"?: string;
  "price_hour_cents": number;
  "price_day_cents": number;
  "price_week_cents": number;
  "price_month_cents": number;
  "cost_hour_cents": number;
  "inventory_total": number;
  "tag"?: string | null;
  "recommended"?: boolean;
}

export interface SKUResponse {
  "id": string;
  "name": string;
  "gpu_model": string;
  "gpu_memory_gb": number;
  "gpu_count": number;
  "vcpu": number;
  "memory_gb": number;
  "system_disk_gb": number;
  "data_disk_gb": number;
  "region": string;
  "zone": string;
  "cpu_vendor": string;
  "price_hour_cents": number;
  "price_day_cents": number;
  "price_week_cents": number;
  "price_month_cents": number;
  "inventory_available": number;
  "status": string;
  "tag": string | null;
  "recommended": boolean;
  "version": number;
}

export interface SKUUpdateRequest {
  "version": number;
  "price_hour_cents"?: number | null;
  "price_day_cents"?: number | null;
  "price_week_cents"?: number | null;
  "price_month_cents"?: number | null;
  "cost_hour_cents"?: number | null;
  "inventory_total"?: number | null;
  "status"?: "draft" | "published" | "unpublished" | "archived" | null;
  "tag"?: string | null;
  "recommended"?: boolean | null;
  "reason"?: string;
}

export interface TaskResponse {
  "id": string;
  "instance_id": string;
  "action": string;
  "status": string;
  "progress": number;
  "attempt_count": number;
  "retry_count": number;
  "error_code": string | null;
  "error_summary": string | null;
  "created_at": string;
  "completed_at": string | null;
}

export interface UnbindIdentityRequest {
  "current_password": string;
}

export interface UsageEventResponse {
  "id": string;
  "request_id": string;
  "user_id": string;
  "model_slug": string;
  "routed_model_slug": string | null;
  "routing_tier": string | null;
  "routing_decision_source": string | null;
  "classifier_model_slug": string | null;
  "classifier_latency_ms": number;
  "replica_label": string | null;
  "prompt_tokens": number;
  "completion_tokens": number;
  "latency_ms": number;
  "cost_micros": number;
  "debit_cents": number;
  "status": string;
  "api_key_id": string | null;
  "conversation_id": string | null;
  "created_at": string;
}

export interface UserResponse {
  "id": string;
  "phone": string | null;
  "email": string | null;
  "nickname": string;
  "balance_cents": number;
  "real_name_status": string;
  "status": string;
}

export interface ValidationError {
  "loc": Array<string | number>;
  "msg": string;
  "type": string;
  "input"?: unknown;
  "ctx"?: Record<string, unknown>;
}

export interface WalletTransactionResponse {
  "id": string;
  "order_id": string | null;
  "transaction_type": string;
  "amount_cents": number;
  "balance_after_cents": number;
  "description": string;
  "created_at": string;
}
