import {
  ANONYMOUS_ID_STORAGE_KEY,
  createAnonymousIdentity,
  initializeAnonymousIdentity,
} from "@/lib/identity";
import {
  CURRENT_CHAT_SESSION_STORAGE_KEY,
  createChatSession,
  initializeCurrentChatSession,
  startNewChatSession,
} from "@/lib/chat-session";
import {
  ChatSessionNotFoundError,
  convertHistoryMessagesToChatMessages,
  fetchChatHistory,
} from "@/lib/chat-history";

const mockRandomUUID = jest.fn();
const mockGetRandomValues = jest.fn((bytes: Uint8Array) => {
  bytes.set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
  return bytes;
});

Object.defineProperty(globalThis, "crypto", {
  value: {
    randomUUID: mockRandomUUID,
    getRandomValues: mockGetRandomValues,
  },
  configurable: true,
});

describe("anonymous identity module", () => {
  beforeEach(() => {
    localStorage.clear();
    mockRandomUUID.mockReset();
    mockRandomUUID.mockReturnValue("local-uuid");
    mockGetRandomValues.mockClear();
  });

  it("creates and stores anonymous_id when localStorage is empty", async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ anonymous_id: "anon_backend" }),
    });

    await expect(initializeAnonymousIdentity({ fetcher })).resolves.toBe("anon_backend");

    expect(fetcher).toHaveBeenCalledWith("http://localhost:34567/api/anonymous-identities", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
    expect(localStorage.getItem(ANONYMOUS_ID_STORAGE_KEY)).toBe("anon_backend");
  });

  it("reuses stored anonymous_id without calling backend", async () => {
    localStorage.setItem(ANONYMOUS_ID_STORAGE_KEY, "anon_existing");
    const fetcher = jest.fn();

    await expect(initializeAnonymousIdentity({ fetcher })).resolves.toBe("anon_existing");

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("falls back to local crypto UUID when anonymous identity API fails", async () => {
    const fetcher = jest.fn().mockRejectedValue(new Error("not implemented"));

    await expect(createAnonymousIdentity({ fetcher })).resolves.toBe("anon_local_local-uuid");
  });

  it("creates a local anonymous_id when randomUUID is unavailable", async () => {
    Object.defineProperty(globalThis, "crypto", {
      value: {
        getRandomValues: mockGetRandomValues,
      },
      configurable: true,
    });
    const fetcher = jest.fn().mockRejectedValue(new Error("not implemented"));

    await expect(createAnonymousIdentity({ fetcher })).resolves.toBe(
      "anon_local_00010203-0405-4607-8809-0a0b0c0d0e0f"
    );

    Object.defineProperty(globalThis, "crypto", {
      value: {
        randomUUID: mockRandomUUID,
        getRandomValues: mockGetRandomValues,
      },
      configurable: true,
    });
  });
});

describe("chat session module", () => {
  beforeEach(() => {
    localStorage.clear();
    mockRandomUUID.mockReset();
    mockRandomUUID.mockReturnValue("session-uuid");
    mockGetRandomValues.mockClear();
  });

  it("creates and stores chat_session_id when localStorage is empty", async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        chat_session_id: "chat_backend",
        title: "新会话",
        created_at: "2026-05-22T10:00:00+08:00",
      }),
    });

    await expect(initializeCurrentChatSession("anon_backend", { fetcher })).resolves.toEqual({
      chatSessionId: "chat_backend",
      title: "新会话",
      createdAt: "2026-05-22T10:00:00+08:00",
    });

    expect(fetcher).toHaveBeenCalledWith("http://localhost:34567/api/chat/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ anonymous_id: "anon_backend" }),
    });
    expect(localStorage.getItem(CURRENT_CHAT_SESSION_STORAGE_KEY)).toBe("chat_backend");
  });

  it("reuses stored chat_session_id without calling backend", async () => {
    localStorage.setItem(CURRENT_CHAT_SESSION_STORAGE_KEY, "chat_existing");
    const fetcher = jest.fn();

    await expect(initializeCurrentChatSession("anon_backend", { fetcher })).resolves.toEqual({
      chatSessionId: "chat_existing",
    });

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("replaces a stored local chat_session_id with a backend session when available", async () => {
    localStorage.setItem(CURRENT_CHAT_SESSION_STORAGE_KEY, "chat_local_old");
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ chat_session_id: "chat_backend_new" }),
    });

    await expect(initializeCurrentChatSession("anon_local", { fetcher })).resolves.toEqual({
      chatSessionId: "chat_backend_new",
      title: undefined,
      createdAt: undefined,
    });

    expect(fetcher).toHaveBeenCalledWith("http://localhost:34567/api/chat/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ anonymous_id: "anon_local" }),
    });
    expect(localStorage.getItem(CURRENT_CHAT_SESSION_STORAGE_KEY)).toBe("chat_backend_new");
  });

  it("falls back to local crypto UUID when chat session API fails", async () => {
    const fetcher = jest.fn().mockResolvedValue({ ok: false, status: 404 });

    await expect(createChatSession("anon_backend", { fetcher })).resolves.toEqual({
      chatSessionId: "chat_local_session-uuid",
    });
  });

  it("starts a new session and replaces the stored current session", async () => {
    localStorage.setItem(CURRENT_CHAT_SESSION_STORAGE_KEY, "chat_old");
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ chat_session_id: "chat_new" }),
    });

    await expect(startNewChatSession("anon_backend", { fetcher })).resolves.toEqual({
      chatSessionId: "chat_new",
      title: undefined,
      createdAt: undefined,
    });

    expect(localStorage.getItem(CURRENT_CHAT_SESSION_STORAGE_KEY)).toBe("chat_new");
  });
});

describe("chat history module", () => {
  it("converts backend history messages to flat ChatMessage fields", () => {
    const messages = convertHistoryMessagesToChatMessages([
      {
        id: "msg_user",
        role: "user",
        content: "百万医疗险怎么选？",
        created_at: "2026-05-22T10:01:00+08:00",
      },
      {
        id: "msg_assistant",
        role: "assistant",
        content: "重点看保障责任、免赔额、续保条件和健康告知。",
        created_at: "2026-05-22T10:01:03+08:00",
        metadata: {
          products: [{ id: "p1", name: "产品A" }],
          sources: [{ title: "来源A", url: "https://example.com", site: "example" }],
          disclaimer: "仅供参考",
        },
      },
      {
        id: "msg_system",
        role: "system",
        content: "ignored",
      },
    ]);

    expect(messages).toEqual([
      {
        id: "msg_user",
        role: "user",
        content: "百万医疗险怎么选？",
        createdAt: "2026-05-22T10:01:00+08:00",
        sources: undefined,
        products: undefined,
        disclaimer: undefined,
      },
      {
        id: "msg_assistant",
        role: "assistant",
        content: "重点看保障责任、免赔额、续保条件和健康告知。",
        createdAt: "2026-05-22T10:01:03+08:00",
        sources: [{ title: "来源A", url: "https://example.com", site: "example" }],
        products: [{ id: "p1", name: "产品A" }],
        disclaimer: "仅供参考",
      },
    ]);
  });

  it("fetches chat history with anonymous_id and chat_session_id", async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        chat_session_id: "chat_backend",
        messages: [{ id: "msg_user", role: "user", content: "你好" }],
      }),
    });

    await expect(fetchChatHistory("anon_backend", "chat_backend", { fetcher })).resolves.toEqual([
      {
        id: "msg_user",
        role: "user",
        content: "你好",
        createdAt: undefined,
        sources: undefined,
        products: undefined,
        disclaimer: undefined,
      },
    ]);

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:34567/api/chat/sessions/chat_backend/messages?anonymous_id=anon_backend",
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );
  });

  it("throws a typed error when backend reports the session is missing", async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(fetchChatHistory("anon_backend", "chat_missing", { fetcher })).rejects.toBeInstanceOf(
      ChatSessionNotFoundError
    );
  });
});
