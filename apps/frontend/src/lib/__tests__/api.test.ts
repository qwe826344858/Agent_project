import { TextDecoder, TextEncoder } from "util";
import { ReadableStream } from "stream/web";

Object.assign(globalThis, { TextDecoder, TextEncoder, ReadableStream });

const ORIGINAL_ENV = process.env;

function textToStream(text: string): any {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function createSSEFetchResponse(): any {
  return {
    ok: true,
    body: textToStream('event: done\ndata: {"requestId":"req_done"}\n\n'),
    text: async () => "",
  };
}

async function importApiWithEnv(env: Record<string, string | undefined> = {}) {
  jest.resetModules();
  process.env = { ...ORIGINAL_ENV };
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_LEGACY_CHAT_URL;
  delete process.env.NEXT_PUBLIC_AGENT_CHAT_URL;

  for (const [key, value] of Object.entries(env)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }

  return import("@/lib/api");
}

describe("sendChatMessage", () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn(() => Promise.resolve(createSSEFetchResponse()));
    Object.defineProperty(globalThis, "fetch", {
      value: fetchMock,
      configurable: true,
    });
  });

  afterAll(() => {
    process.env = ORIGINAL_ENV;
  });

  it("defaults to the legacy chat endpoint and keeps legacy-compatible body fields", async () => {
    const { sendChatMessage } = await importApiWithEnv();

    await sendChatMessage("百万医疗险怎么选？", {}, {
      anonymousId: "anon_1",
      chatSessionId: "chat_1",
      requestId: "req_1",
      action: "ask_product_followup",
      productUrl: "https://example.com/product-a",
      productName: "产品A",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:34567/api/chat",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
      })
    );

    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(requestBody).toEqual({
      message: "百万医疗险怎么选？",
      anonymous_id: "anon_1",
      chat_session_id: "chat_1",
      sessionId: "chat_1",
      requestId: "req_1",
      action: "ask_product_followup",
      productUrl: "https://example.com/product-a",
      productName: "产品A",
    });
  });

  it("uses the agent chat endpoint and sends the agent request body shape", async () => {
    const { sendChatMessage } = await importApiWithEnv();

    await sendChatMessage("查看这个产品详情", {}, {
      backendMode: "agent_chat",
      anonymousId: "anon_agent",
      chatSessionId: "chat_agent",
      requestId: "req_agent",
      action: "view_product_detail",
      productUrl: "https://example.com/product-b",
      productName: "产品B",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:34567/api/agent/chat");

    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(requestBody).toEqual({
      message: "查看这个产品详情",
      anonymous_id: "anon_agent",
      chat_session_id: "chat_agent",
      stream: true,
      metadata: { source: "web" },
      requestId: "req_agent",
      action: "view_product_detail",
      product_url: "https://example.com/product-b",
      product_name: "产品B",
    });
  });

  it("supports configured legacy and agent chat endpoints", async () => {
    const { sendChatMessage } = await importApiWithEnv({
      NEXT_PUBLIC_LEGACY_CHAT_URL: "/custom/legacy-chat",
      NEXT_PUBLIC_AGENT_CHAT_URL: "https://api.example.test/agent-chat",
    });

    await sendChatMessage("旧链路", {}, { sessionId: "legacy_session" });
    await sendChatMessage("新链路", {}, {
      backendMode: "agent_chat",
      sessionId: "agent_session",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:34567/custom/legacy-chat");
    expect(fetchMock.mock.calls[1][0]).toBe("https://api.example.test/agent-chat");

    const agentRequestBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(agentRequestBody).toEqual(expect.objectContaining({
      anonymous_id: "",
      chat_session_id: "agent_session",
      stream: true,
      metadata: { source: "web" },
    }));
  });
});
