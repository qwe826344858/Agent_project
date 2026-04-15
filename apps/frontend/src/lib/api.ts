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
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8000` : "");

/** sendChatMessage 的可选配置 */
export interface SendChatMessageOptions {
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

/**
 * 发送聊天消息并消费 SSE 流式响应
 *
 * 调用 POST /api/chat 接口，将用户消息发送到后端，并通过 SSE handlers
 * 实时接收并处理流式返回的各类事件。
 *
 * @param message - 用户输入的聊天消息
 * @param handlers - SSE 事件处理回调集合
 * @param options - 可选配置（sessionId、requestId、signal）
 */
export async function sendChatMessage(
  message: string,
  handlers: SSEHandlers,
  options?: SendChatMessageOptions
): Promise<void> {
  const url = `${API_BASE_URL}/api/chat`;

  // 构建请求体
  const body: Record<string, string> = { message };
  if (options?.sessionId) {
    body.sessionId = options.sessionId;
  }
  if (options?.requestId) {
    body.requestId = options.requestId;
  }
  if (options?.action) body.action = options.action;
  if (options?.productUrl) body.productUrl = options.productUrl;
  if (options?.productName) body.productName = options.productName;

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
  const url = `${API_BASE_URL}/api/suggestions`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`获取推荐问题失败 (${response.status})`);
  }

  const data: SuggestionsResponse = await response.json();
  return data.suggestions;
}
