/** 消息角色 */
export type MessageRole = "user" | "assistant";

/** 来源条目 */
export interface SourceItem {
  title: string;
  url: string;
  site: string;
  product_url?: string;
}

/** SSE status 事件的 stage，后端 Agent/DeepAgent 链路可扩展新阶段 */
export type ThinkingStage = string;

/** SSE 事件类型 */
export type SSEEventType = "status" | "delta" | "sources" | "disclaimer" | "done" | "error" | "products" | "products_update" | "detail_items";

/** Agent SSE 可选追踪字段 */
export interface SSEAgentTraceFields {
  agent_id?: string;
  trace_id?: string;
  requestId?: string;
  request_id?: string;
}

/** SSE 事件载荷 */
export interface SSEStatusPayload extends SSEAgentTraceFields {
  stage?: ThinkingStage;
  message?: string;
}

export interface SSEDeltaPayload extends SSEAgentTraceFields {
  text: string;
}

export interface SSESourcesPayload extends SSEAgentTraceFields {
  items: SourceItem[];
}

export interface SSEDisclaimerPayload extends SSEAgentTraceFields {
  text: string;
}

export interface SSEDonePayload extends SSEAgentTraceFields {
  chat_session_id?: string;
  sessionId?: string;
}

export interface SSEErrorPayload extends SSEAgentTraceFields {
  code: string;
  message: string;
  requestId?: string;
}

/** 产品推荐卡片（双通道方案） */
export interface ProductCard {
  id: string;
  name: string;
  company: string;
  price: string | null;
  priceLabel: string;
  tags: string[];
  url: string;
  platform: string;
  brief: string;
}

/** 单项保障 — 产品详情提取 */
export interface DutyItem {
  name: string;
  coverage: string;
  description: string;
  is_optional: boolean;
}

/** SSE detail_items 事件载荷 */
export interface SSEDetailItemsPayload extends SSEAgentTraceFields {
  product_name: string;
  duties: DutyItem[];
}

/** SSE products 事件载荷 */
export interface SSEProductsPayload extends SSEAgentTraceFields {
  items: ProductCard[];
}

/** SSE products_update 事件载荷 */
export interface SSEProductsUpdatePayload extends SSEAgentTraceFields {
  items: Partial<ProductCard>[];
}

/** ChatMessage 扩展 — 包含产品卡片 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt?: string;
  sources?: SourceItem[];
  disclaimer?: string;
  isStreaming?: boolean;
  error?: string;
  products?: ProductCard[];
  duties?: DutyItem[];  // 新增：产品保障详情
  detailProductName?: string;  // 保障详情对应的产品名称
}

/** 推荐问题响应 */
export interface SuggestionsResponse {
  suggestions: string[];
}
