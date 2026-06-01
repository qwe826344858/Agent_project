/**
 * API 客户端
 *
 * 封装与后端服务的 HTTP 通信，包括 SSE 流式聊天和普通 REST 请求。
 */

import type { SuggestionsResponse } from "@/types/chat";
import { createSSEParser, type SSEHandlers } from "@/lib/sse-parser";

/** API 基础 URL
 * SSE 流式请求不能走 Next.js rewrites 代理（会缓冲响应），
 * 需要前端直连后端 API。
 * 开发模式下通过 NEXT_PUBLIC_API_BASE_URL 配置后端地址。
 */
const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "";
const CONFIGURED_LEGACY_CHAT_URL =
  process.env.NEXT_PUBLIC_LEGACY_CHAT_URL?.trim() || "/api/chat";
const CONFIGURED_AGENT_CHAT_URL =
  process.env.NEXT_PUBLIC_AGENT_CHAT_URL?.trim() || "/api/agent/chat";
const DEFAULT_API_PORT = "34567";
const SUGGESTIONS_TIMEOUT_MS = 5000;

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function isAbsoluteUrl(url: string): boolean {
  return /^[a-z][a-z\d+\-.]*:\/\//i.test(url);
}

function normalizeApiBaseUrl(baseUrl: string): string {
  if (!baseUrl) return "";
  if (isAbsoluteUrl(baseUrl)) {
    return baseUrl;
  }

  return `http://${baseUrl}`;
}

function getBrowserApiBaseUrl(): string {
  const pageHost = window.location.hostname;

  if (!CONFIGURED_API_BASE_URL) {
    return `${window.location.protocol}//${pageHost}:${DEFAULT_API_PORT}`;
  }

  try {
    const url = new URL(normalizeApiBaseUrl(CONFIGURED_API_BASE_URL), window.location.origin);
    const configuredHost = url.hostname;
    const pointsToInternalDockerHost =
      configuredHost === "backend" || configuredHost === "0.0.0.0";
    const pointsToLocalhostFromRemotePage =
      isLoopbackHost(configuredHost) && !isLoopbackHost(pageHost);

    if (pointsToInternalDockerHost || pointsToLocalhostFromRemotePage) {
      url.protocol = window.location.protocol;
      url.hostname = pageHost;
      url.port = pointsToInternalDockerHost ? DEFAULT_API_PORT : url.port || DEFAULT_API_PORT;
    }

    return url.origin;
  } catch {
    return `${window.location.protocol}//${pageHost}:${DEFAULT_API_PORT}`;
  }
}

function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return normalizeApiBaseUrl(CONFIGURED_API_BASE_URL).replace(/\/$/, "");
  }

  return getBrowserApiBaseUrl().replace(/\/$/, "");
}

export function buildApiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

export type ChatBackendMode = "legacy_chat" | "agent_chat";

function normalizeEndpointUrl(endpoint: string): string {
  const trimmedEndpoint = endpoint.trim();
  if (isAbsoluteUrl(trimmedEndpoint)) {
    return trimmedEndpoint;
  }

  const path = trimmedEndpoint.startsWith("/") ? trimmedEndpoint : `/${trimmedEndpoint}`;
  return buildApiUrl(path);
}

function getChatEndpointUrl(backendMode: ChatBackendMode): string {
  return normalizeEndpointUrl(
    backendMode === "agent_chat" ? CONFIGURED_AGENT_CHAT_URL : CONFIGURED_LEGACY_CHAT_URL
  );
}

/** sendChatMessage 的可选配置 */
export interface SendChatMessageOptions {
  /** 后端聊天链路，默认使用旧链路 */
  backendMode?: ChatBackendMode;
  /** 匿名用户 ID，用于后端关联当前浏览器用户 */
  anonymousId?: string;
  /** 当前聊天会话 ID，用于后端保存和恢复历史 */
  chatSessionId?: string;
  /** 会话 ID，用于关联多轮对话 */
  sessionId?: string;
  /** 请求 ID，用于追踪和取消请求 */
  requestId?: string;
  /** AbortSignal，用于取消正在进行的请求 */
  signal?: AbortSignal;
  /** 动作类型（如查看产品详情） */
  action?: string;
  /** 产品投保链接 */
  productUrl?: string;
  /** 产品名称 */
  productName?: string;
}

function buildLegacyChatRequestBody(
  message: string,
  options?: SendChatMessageOptions
): Record<string, unknown> {
  const body: Record<string, unknown> = { message };
  if (options?.anonymousId) {
    body.anonymous_id = options.anonymousId;
  }
  if (options?.chatSessionId) {
    body.chat_session_id = options.chatSessionId;
    body.sessionId = options.chatSessionId;
  }
  if (options?.sessionId) {
    body.sessionId = options.sessionId;
    if (!body.chat_session_id) {
      body.chat_session_id = options.sessionId;
    }
  }
  if (options?.requestId) {
    body.requestId = options.requestId;
  }
  if (options?.action) body.action = options.action;
  if (options?.productUrl) body.productUrl = options.productUrl;
  if (options?.productName) body.productName = options.productName;

  return body;
}

function buildAgentChatRequestBody(
  message: string,
  options?: SendChatMessageOptions
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    message,
    anonymous_id: options?.anonymousId ?? "",
    chat_session_id: options?.chatSessionId ?? options?.sessionId ?? "",
    stream: true,
    metadata: { source: "web" },
  };

  if (options?.requestId) {
    body.requestId = options.requestId;
  }
  if (options?.action) body.action = options.action;
  if (options?.productUrl) body.product_url = options.productUrl;
  if (options?.productName) body.product_name = options.productName;

  return body;
}

function buildChatRequestBody(
  message: string,
  backendMode: ChatBackendMode,
  options?: SendChatMessageOptions
): Record<string, unknown> {
  if (backendMode === "agent_chat") {
    return buildAgentChatRequestBody(message, options);
  }

  return buildLegacyChatRequestBody(message, options);
}

/**
 * 发送聊天消息并消费 SSE 流式响应
 *
 * 调用配置的聊天接口，将用户消息发送到后端，并通过 SSE handlers
 * 实时接收并处理流式返回的各类事件。默认使用旧链路 /api/chat。
 *
 * @param message - 用户输入的聊天消息
 * @param handlers - SSE 事件处理回调集合
 * @param options - 可选配置（backendMode、sessionId、requestId、signal）
 */
export async function sendChatMessage(
  message: string,
  handlers: SSEHandlers,
  options?: SendChatMessageOptions
): Promise<void> {
  const backendMode = options?.backendMode ?? "legacy_chat";
  const url = getChatEndpointUrl(backendMode);
  const body = buildChatRequestBody(message, backendMode, options);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: options?.signal,
  });

  // 检查 HTTP 响应状态
  if (!response.ok) {
    const errorText = await response.text().catch(() => "未知错误");
    handlers.onError?.({
      code: `HTTP_${response.status}`,
      message: `请求失败 (${response.status}): ${errorText}`,
    });
    return;
  }

  // 确保响应体存在
  if (!response.body) {
    handlers.onError?.({
      code: "NO_BODY",
      message: "响应体为空，无法读取 SSE 流",
    });
    return;
  }

  // 使用 SSE 解析器消费流式响应
  const parser = createSSEParser(handlers);
  await parser(response.body);
}

/**
 * 获取推荐问题列表
 *
 * 调用 GET /api/suggestions 接口，返回推荐问题的字符串数组。
 *
 * @returns 推荐问题列表
 */
export async function fetchSuggestions(): Promise<string[]> {
  const url = buildApiUrl("/api/suggestions");
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(
    () => controller.abort(),
    SUGGESTIONS_TIMEOUT_MS,
  );

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`获取推荐问题失败 (${response.status})`);
    }

    const data: SuggestionsResponse = await response.json();
    return data.suggestions;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}
