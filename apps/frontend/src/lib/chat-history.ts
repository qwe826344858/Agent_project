import type { ChatMessage, MessageRole, ProductCard, SourceItem } from "@/types/chat";
import { buildApiUrl } from "@/lib/api";

export class ChatSessionNotFoundError extends Error {
  constructor(chatSessionId: string) {
    super(`Chat session not found: ${chatSessionId}`);
    this.name = "ChatSessionNotFoundError";
  }
}

interface ChatHistoryOptions {
  fetcher?: typeof fetch;
}

interface BackendHistoryResponse {
  chat_session_id?: unknown;
  messages?: unknown;
}

interface BackendHistoryMessage {
  id?: unknown;
  role?: unknown;
  content?: unknown;
  created_at?: unknown;
  metadata?: {
    products?: unknown;
    sources?: unknown;
    disclaimer?: unknown;
  } | null;
  products?: unknown;
  sources?: unknown;
  disclaimer?: unknown;
}

function isMessageRole(role: unknown): role is MessageRole {
  return role === "user" || role === "assistant";
}

function normalizeSources(value: unknown): SourceItem[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      title: typeof item.title === "string" ? item.title : "",
      url: typeof item.url === "string" ? item.url : "",
      site: typeof item.site === "string" ? item.site : "",
    }))
    .filter((item) => item.title || item.url || item.site);
}

function normalizeProducts(value: unknown): ProductCard[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value.filter((item): item is ProductCard => typeof item === "object" && item !== null);
}

export function convertHistoryMessagesToChatMessages(messages: unknown): ChatMessage[] {
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages.reduce<ChatMessage[]>((acc, rawMessage, index) => {
    if (typeof rawMessage !== "object" || rawMessage === null) {
      return acc;
    }

    const message = rawMessage as BackendHistoryMessage;
    if (!isMessageRole(message.role)) {
      return acc;
    }

    const metadata = message.metadata ?? {};
    const sources = normalizeSources(message.sources ?? metadata.sources);
    const products = normalizeProducts(message.products ?? metadata.products);
    const disclaimer = message.disclaimer ?? metadata.disclaimer;

    acc.push({
      id: typeof message.id === "string" && message.id.trim() ? message.id : `history_${index}`,
      role: message.role,
      content: typeof message.content === "string" ? message.content : "",
      createdAt: typeof message.created_at === "string" ? message.created_at : undefined,
      sources,
      products,
      disclaimer: typeof disclaimer === "string" ? disclaimer : undefined,
    });

    return acc;
  }, []);
}

export async function fetchChatHistory(
  anonymousId: string,
  chatSessionId: string,
  options: ChatHistoryOptions = {}
): Promise<ChatMessage[]> {
  const fetcher = options.fetcher ?? fetch;
  const query = new URLSearchParams({ anonymous_id: anonymousId });
  const url = buildApiUrl(
    `/api/chat/sessions/${encodeURIComponent(chatSessionId)}/messages?${query.toString()}`
  );
  const response = await fetcher(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    throw new ChatSessionNotFoundError(chatSessionId);
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch chat history (${response.status})`);
  }

  const data = (await response.json()) as BackendHistoryResponse;
  return convertHistoryMessagesToChatMessages(data.messages);
}
