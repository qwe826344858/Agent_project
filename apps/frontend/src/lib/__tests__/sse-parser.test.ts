/**
 * SSE 解析器单元测试
 */

// jsdom 环境下缺少 Web Streams API 和 TextEncoder/TextDecoder，需要补充 polyfill
import { TextEncoder, TextDecoder } from "util";
import { ReadableStream } from "stream/web";

Object.assign(globalThis, { TextEncoder, TextDecoder, ReadableStream });

import { parseSSELine, createSSEParser, type SSEHandlers } from "@/lib/sse-parser";
import type { SSEStatusPayload } from "@/types/chat";

// ============================================================================
// parseSSELine 测试
// ============================================================================

describe("parseSSELine", () => {
  it("应正确解析 event 行", () => {
    const result = parseSSELine("event: status");
    expect(result).toEqual({ field: "event", value: "status" });
  });

  it("应正确解析 data 行", () => {
    const result = parseSSELine('data: {"text":"hello"}');
    expect(result).toEqual({ field: "data", value: '{"text":"hello"}' });
  });

  it("应正确解析不带空格的 event 行", () => {
    const result = parseSSELine("event:delta");
    expect(result).toEqual({ field: "event", value: "delta" });
  });

  it("应正确解析不带空格的 data 行", () => {
    const result = parseSSELine('data:{"text":"hi"}');
    expect(result).toEqual({ field: "data", value: '{"text":"hi"}' });
  });

  it("应忽略空行（返回 null）", () => {
    expect(parseSSELine("")).toBeNull();
    expect(parseSSELine("  ")).toBeNull();
    expect(parseSSELine("\t")).toBeNull();
  });

  it("应忽略注释行（以冒号开头）", () => {
    expect(parseSSELine(": this is a comment")).toBeNull();
    expect(parseSSELine(":keep-alive")).toBeNull();
  });

  it("应忽略无法识别的行", () => {
    expect(parseSSELine("unknown: value")).toBeNull();
    expect(parseSSELine("just some text")).toBeNull();
  });
});

// ============================================================================
// createSSEParser 测试
// ============================================================================

describe("createSSEParser", () => {
  /**
   * 辅助函数：将文本转为 ReadableStream<Uint8Array>
   */
  // Node.js stream/web 的 ReadableStream 与 DOM 类型存在差异，返回 any 绕过
  function textToStream(text: string): any {
    const encoder = new TextEncoder();
    return new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(text));
        controller.close();
      },
    });
  }

  /**
   * 辅助函数：将文本按块拆分后转为 ReadableStream，模拟网络分片
   */
  function chunkedTextToStream(chunks: string[]): any {
    const encoder = new TextEncoder();
    return new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });
  }

  it("应正确分发 status 事件", async () => {
    const handlers: SSEHandlers = {
      onStatus: jest.fn(),
    };

    const stream = textToStream(
      'event: status\ndata: {"stage":"analyzing","message":"正在分析问题"}\n\n'
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onStatus).toHaveBeenCalledTimes(1);
    expect(handlers.onStatus).toHaveBeenCalledWith({
      stage: "analyzing",
      message: "正在分析问题",
    });
  });

  it("应兼容 agent SSE 追踪字段", async () => {
    const handlers: SSEHandlers = {
      onStatus: jest.fn(),
    };
    const statusPayload: SSEStatusPayload = {
      stage: "searching",
      message: "正在调用搜索 Agent",
      agent_id: "search_agent",
      trace_id: "trace_123",
    };

    const stream = textToStream(
      `event: status\ndata: ${JSON.stringify(statusPayload)}\n\n`
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onStatus).toHaveBeenCalledTimes(1);
    expect(handlers.onStatus).toHaveBeenCalledWith(statusPayload);
  });

  it("应正确分发 delta 事件", async () => {
    const handlers: SSEHandlers = {
      onDelta: jest.fn(),
    };

    const stream = textToStream(
      'event: delta\ndata: {"text":"你好"}\n\n'
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onDelta).toHaveBeenCalledTimes(1);
    expect(handlers.onDelta).toHaveBeenCalledWith({ text: "你好" });
  });

  it("应正确分发 sources 事件", async () => {
    const handlers: SSEHandlers = {
      onSources: jest.fn(),
    };

    const sourcesData = {
      items: [
        {
          title: "示例文章",
          url: "https://example.com/source",
          site: "example.com",
          product_url: "https://example.com/product",
        },
      ],
    };

    const stream = textToStream(
      `event: sources\ndata: ${JSON.stringify(sourcesData)}\n\n`
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onSources).toHaveBeenCalledTimes(1);
    expect(handlers.onSources).toHaveBeenCalledWith(sourcesData);
  });

  it("应正确分发 disclaimer 事件", async () => {
    const handlers: SSEHandlers = {
      onDisclaimer: jest.fn(),
    };

    const stream = textToStream(
      'event: disclaimer\ndata: {"text":"以上内容仅供参考"}\n\n'
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onDisclaimer).toHaveBeenCalledTimes(1);
    expect(handlers.onDisclaimer).toHaveBeenCalledWith({
      text: "以上内容仅供参考",
    });
  });

  it("应正确分发 done 事件", async () => {
    const handlers: SSEHandlers = {
      onDone: jest.fn(),
    };

    const stream = textToStream(
      'event: done\ndata: {"requestId":"req-123"}\n\n'
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onDone).toHaveBeenCalledTimes(1);
    expect(handlers.onDone).toHaveBeenCalledWith({ requestId: "req-123" });
  });

  it("应正确分发 error 事件", async () => {
    const handlers: SSEHandlers = {
      onError: jest.fn(),
    };

    const stream = textToStream(
      'event: error\ndata: {"code":"RATE_LIMIT","message":"请求过于频繁","requestId":"req-456"}\n\n'
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError).toHaveBeenCalledWith({
      code: "RATE_LIMIT",
      message: "请求过于频繁",
      requestId: "req-456",
    });
  });

  it("应正确处理多个连续事件", async () => {
    const handlers: SSEHandlers = {
      onStatus: jest.fn(),
      onDelta: jest.fn(),
      onDone: jest.fn(),
    };

    const sseText = [
      'event: status\ndata: {"stage":"analyzing","message":"分析中"}\n\n',
      'event: delta\ndata: {"text":"第一段"}\n\n',
      'event: delta\ndata: {"text":"第二段"}\n\n',
      'event: done\ndata: {"requestId":"req-789"}\n\n',
    ].join("");

    const stream = textToStream(sseText);
    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onStatus).toHaveBeenCalledTimes(1);
    expect(handlers.onDelta).toHaveBeenCalledTimes(2);
    expect(handlers.onDelta).toHaveBeenNthCalledWith(1, { text: "第一段" });
    expect(handlers.onDelta).toHaveBeenNthCalledWith(2, { text: "第二段" });
    expect(handlers.onDone).toHaveBeenCalledTimes(1);
  });

  it("应正确处理跨 chunk 拆分的行", async () => {
    const handlers: SSEHandlers = {
      onDelta: jest.fn(),
    };

    // 模拟网络分片：一行 SSE 数据被拆分到两个 chunk 中
    const stream = chunkedTextToStream([
      'event: delta\ndata: {"te',
      'xt":"完整内容"}\n\n',
    ]);

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onDelta).toHaveBeenCalledTimes(1);
    expect(handlers.onDelta).toHaveBeenCalledWith({ text: "完整内容" });
  });

  it("应忽略注释行和空行", async () => {
    const handlers: SSEHandlers = {
      onDelta: jest.fn(),
    };

    const sseText = [
      ": this is a comment\n",
      "\n",
      'event: delta\ndata: {"text":"有效数据"}\n\n',
    ].join("");

    const stream = textToStream(sseText);
    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onDelta).toHaveBeenCalledTimes(1);
    expect(handlers.onDelta).toHaveBeenCalledWith({ text: "有效数据" });
  });

  it("当 JSON 解析失败时应调用 onError", async () => {
    const handlers: SSEHandlers = {
      onError: jest.fn(),
    };

    const stream = textToStream(
      "event: delta\ndata: {invalid json}\n\n"
    );

    const parser = createSSEParser(handlers);
    await parser(stream);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError).toHaveBeenCalledWith(
      expect.objectContaining({
        code: "PARSE_ERROR",
      })
    );
  });

  it("缺少 handler 时不应抛出异常", async () => {
    // 传入空 handlers，确保不会因为回调不存在而报错
    const handlers: SSEHandlers = {};

    const stream = textToStream(
      'event: delta\ndata: {"text":"无处理器"}\n\n'
    );

    const parser = createSSEParser(handlers);

    // 不应抛出异常
    await expect(parser(stream)).resolves.toBeUndefined();
  });
});
