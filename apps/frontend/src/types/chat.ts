/** 消息角色 */
export type MessageRole = "user" | "assistant";

/** 来源条目 */
export interface SourceItem {
  title: string;
  url: string;
  site: string;
}

/** SSE status 事件的 stage 枚举 */
export type ThinkingStage = "analyzing" | "searching" | "reading" | "answering";

/** SSE 事件类型 */
export type SSEEventType = "status" | "delta" | "sources" | "disclaimer" | "done" | "error" | "products" | "products_update";

/** SSE 事件载荷 */
export interface SSEStatusPayload {
  stage: ThinkingStage;
  message: string;
}

export interface SSEDeltaPayload {
  text: string;
}

export interface SSESourcesPayload {
  items: SourceItem[];
}

export interface SSEDisclaimerPayload {
  text: string;
}

export interface SSEDonePayload {
  requestId: string;
}

export interface SSEErrorPayload {
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

/** SSE products 事件载荷 */
export interface SSEProductsPayload {
  items: ProductCard[];
}

/** SSE products_update 事件载荷 */
export interface SSEProductsUpdatePayload {
  items: Partial<ProductCard>[];
}

/** ChatMessage 扩展 — 包含产品卡片 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceItem[];
  disclaimer?: string;
  isStreaming?: boolean;
  error?: string;
  products?: ProductCard[];
}

/** 推荐问题响应 */
export interface SuggestionsResponse {
  suggestions: string[];
}
