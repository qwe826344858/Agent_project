/**
 * SSE（Server-Sent Events）解析器
 *
 * 负责将原始 SSE 文本流解析为结构化事件，并分发给对应的回调处理函数。
 */

import type {
  SSEEventType,
  SSEStatusPayload,
  SSEDeltaPayload,
  SSESourcesPayload,
  SSEDisclaimerPayload,
  SSEDonePayload,
  SSEErrorPayload,
  SSEProductsPayload,
  SSEProductsUpdatePayload,
} from "@/types/chat";

/** SSE 事件处理回调集合 */
export interface SSEHandlers {
  onStatus?: (data: SSEStatusPayload) => void;
  onDelta?: (data: SSEDeltaPayload) => void;
  onSources?: (data: SSESourcesPayload) => void;
  onDisclaimer?: (data: SSEDisclaimerPayload) => void;
  onDone?: (data: SSEDonePayload) => void;
  onError?: (data: SSEErrorPayload) => void;
  // 产品卡片事件
  onProducts?: (data: SSEProductsPayload) => void;
  onProductsUpdate?: (data: SSEProductsUpdatePayload) => void;
}

/** parseSSELine 的返回值类型 */
export interface SSELineResult {
  event: SSEEventType;
  data: string;
}

/**
 * 解析单行 SSE 文本
 *
 * SSE 协议中，每条消息由 "event:" 和 "data:" 两行组成，空行作为消息分隔符。
 * 此函数不处理完整消息的组装，仅提取单行的字段名和值。
 *
 * @param line - 原始 SSE 文本行
 * @returns 当行为 event 或 data 字段时返回对应的 key/value，否则返回 null
 */
export function parseSSELine(
  line: string
): { field: "event"; value: string } | { field: "data"; value: string } | null {
  // 忽略空行（消息分隔符）
  if (!line || line.trim() === "") {
    return null;
  }

  // 忽略注释行（以冒号开头）
  if (line.startsWith(":")) {
    return null;
  }

  // 解析 "event: xxx" 行
  if (line.startsWith("event:")) {
    const value = line.slice("event:".length).trim();
    return { field: "event", value };
  }

  // 解析 "data: xxx" 行
  if (line.startsWith("data:")) {
    const value = line.slice("data:".length).trim();
    return { field: "data", value };
  }

  // 无法识别的行，忽略
  return null;
}

/**
 * 根据事件类型将解析后的数据分发到对应的回调处理函数
 *
 * @param event - SSE 事件类型
 * @param data - JSON 格式的数据字符串
 * @param handlers - 事件处理回调集合
 */
function dispatchEvent(
  event: SSEEventType,
  data: string,
  handlers: SSEHandlers
): void {
  try {
    const parsed = JSON.parse(data);

    switch (event) {
      case "status":
        handlers.onStatus?.(parsed as SSEStatusPayload);
        break;
      case "delta":
        handlers.onDelta?.(parsed as SSEDeltaPayload);
        break;
      case "sources":
        handlers.onSources?.(parsed as SSESourcesPayload);
        break;
      case "disclaimer":
        handlers.onDisclaimer?.(parsed as SSEDisclaimerPayload);
        break;
      case "done":
        handlers.onDone?.(parsed as SSEDonePayload);
        break;
      case "error":
        handlers.onError?.(parsed as SSEErrorPayload);
        break;
      case "products":
        handlers.onProducts?.(parsed as SSEProductsPayload);
        break;
      case "products_update":
        handlers.onProductsUpdate?.(parsed as SSEProductsUpdatePayload);
        break;
      default:
        // 未知事件类型，静默忽略
        break;
    }
  } catch {
    // JSON 解析失败时，通过 onError 回调通知调用方
    handlers.onError?.({
      code: "PARSE_ERROR",
      message: `SSE 数据解析失败: ${data}`,
    });
  }
}

/**
 * 创建 SSE 解析器
 *
 * 返回一个 async 函数，可消费 ReadableStream<Uint8Array> 并将其中的 SSE 事件
 * 分发到对应的回调处理函数。
 *
 * @param handlers - 事件处理回调集合
 * @returns 消费 ReadableStream 的 async 函数
 */
export function createSSEParser(
  handlers: SSEHandlers
): (stream: ReadableStream<Uint8Array>) => Promise<void> {
  return async (stream: ReadableStream<Uint8Array>) => {
    const reader = stream.getReader();
    const decoder = new TextDecoder("utf-8");

    // 用于缓存未完成的行（TCP 分片可能导致一行被拆分到多个 chunk 中）
    let buffer = "";
    // 当前正在组装的事件类型
    let currentEvent: SSEEventType | null = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 将二进制数据解码并追加到缓冲区
        buffer += decoder.decode(value, { stream: true });

        // 按换行符拆分，处理 \r\n 和 \n 两种行结尾
        const lines = buffer.split(/\r?\n/);

        // 最后一个元素可能是不完整的行，保留在缓冲区
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          // 空行表示一条 SSE 消息结束，重置当前事件
          if (line.trim() === "") {
            currentEvent = null;
            continue;
          }

          const result = parseSSELine(line);
          if (!result) continue;

          if (result.field === "event") {
            // 记录当前事件类型
            currentEvent = result.value as SSEEventType;
          } else if (result.field === "data" && currentEvent) {
            // 收到 data 行后，立即分发事件
            dispatchEvent(currentEvent, result.value, handlers);
          }
        }
      }

      // 处理缓冲区中可能残留的最后一行
      if (buffer.trim()) {
        const result = parseSSELine(buffer);
        if (result?.field === "data" && currentEvent) {
          dispatchEvent(currentEvent, result.value, handlers);
        }
      }
    } finally {
      reader.releaseLock();
    }
  };
}
