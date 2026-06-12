import { buildApiUrl } from "@/lib/api";
import { createLocalUuid } from "@/lib/local-id";

export const CURRENT_CHAT_SESSION_STORAGE_KEY = "smartinsure_current_chat_session_id";

export interface ChatSession {
  chatSessionId: string;
  title?: string;
  createdAt?: string;
}

interface ChatSessionResponse {
  chat_session_id?: unknown;
  title?: unknown;
  created_at?: unknown;
}

interface ChatSessionOptions {
  fetcher?: typeof fetch;
}

function getStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function createLocalChatSessionId(): string {
  return `chat_local_${createLocalUuid()}`;
}

export function isLocalChatSessionId(chatSessionId: string): boolean {
  return chatSessionId.startsWith("chat_local_");
}

export function getStoredChatSessionId(): string | null {
  const value = getStorage()?.getItem(CURRENT_CHAT_SESSION_STORAGE_KEY)?.trim();
  return value || null;
}

export function saveCurrentChatSessionId(chatSessionId: string): void {
  getStorage()?.setItem(CURRENT_CHAT_SESSION_STORAGE_KEY, chatSessionId);
}

export function clearCurrentChatSessionId(): void {
  getStorage()?.removeItem(CURRENT_CHAT_SESSION_STORAGE_KEY);
}

export function switchCurrentChatSession(chatSessionId: string): void {
  saveCurrentChatSessionId(chatSessionId);
}

export async function createChatSession(anonymousId: string, options: ChatSessionOptions = {}): Promise<ChatSession> {
  const fetcher = options.fetcher ?? fetch;

  try {
    const response = await fetcher(buildApiUrl("/api/chat/sessions"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ anonymous_id: anonymousId }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create chat session (${response.status})`);
    }

    const data = (await response.json()) as ChatSessionResponse;
    if (typeof data.chat_session_id === "string" && data.chat_session_id.trim()) {
      return {
        chatSessionId: data.chat_session_id,
        title: typeof data.title === "string" ? data.title : undefined,
        createdAt: typeof data.created_at === "string" ? data.created_at : undefined,
      };
    }
  } catch {
    return { chatSessionId: createLocalChatSessionId() };
  }

  return { chatSessionId: createLocalChatSessionId() };
}

export async function initializeCurrentChatSession(
  anonymousId: string,
  options: ChatSessionOptions = {}
): Promise<ChatSession> {
  const storedChatSessionId = getStoredChatSessionId();
  if (storedChatSessionId) {
    if (isLocalChatSessionId(storedChatSessionId)) {
      const session = await createChatSession(anonymousId, options);
      saveCurrentChatSessionId(session.chatSessionId);
      return session;
    }

    return { chatSessionId: storedChatSessionId };
  }

  const session = await createChatSession(anonymousId, options);
  saveCurrentChatSessionId(session.chatSessionId);
  return session;
}

export async function startNewChatSession(anonymousId: string, options: ChatSessionOptions = {}): Promise<ChatSession> {
  const session = await createChatSession(anonymousId, options);
  saveCurrentChatSessionId(session.chatSessionId);
  return session;
}
