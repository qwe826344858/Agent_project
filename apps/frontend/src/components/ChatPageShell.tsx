"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage, ThinkingStage, ProductCard } from "@/types/chat";
import { sendChatMessage, fetchSuggestions, type ChatBackendMode } from "@/lib/api";
import { initializeAnonymousIdentity } from "@/lib/identity";
import {
  clearCurrentChatSessionId,
  initializeCurrentChatSession,
  isLocalChatSessionId,
  saveCurrentChatSessionId,
  startNewChatSession,
} from "@/lib/chat-session";
import { ChatSessionNotFoundError, fetchChatHistory } from "@/lib/chat-history";
import ChatInput from "@/components/ChatInput";
import ChatMessageList from "@/components/ChatMessageList";
import ThinkingStatus from "@/components/ThinkingStatus";
import SuggestionList from "@/components/SuggestionList";
import ProductPanel from "@/components/ProductPanel";

interface ChatPageShellProps {
  backendMode?: ChatBackendMode;
  modeLabel?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  fallbackSuggestions?: string[];
}

/** 生成唯一消息 ID */
function genId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

type SessionIdentifiers = {
  anonymousId: string;
  chatSessionId: string;
};

const DEFAULT_SUGGESTIONS = [
  "重疾险和医疗险有什么区别？",
  "百万医疗险怎么选？",
  "什么是免赔额？",
  "意外险通常保哪些场景？",
  "等待期是什么意思？",
];

type ProductEventItem = Partial<ProductCard> & {
  price_label?: string | null;
  priceLabel?: string | null;
};

function normalizeProductEventItem(product: ProductEventItem, index: number): ProductCard {
  const name = typeof product.name === "string" && product.name.trim()
    ? product.name
    : "未命名产品";
  const url = typeof product.url === "string" ? product.url : "";
  const tags = Array.isArray(product.tags)
    ? product.tags.filter((tag): tag is string => typeof tag === "string" && tag.trim().length > 0)
    : [];
  const priceLabel =
    (typeof product.price_label === "string" && product.price_label.trim()) ||
    (typeof product.priceLabel === "string" && product.priceLabel.trim()) ||
    "加载中";

  return {
    id: typeof product.id === "string" && product.id.trim()
      ? product.id
      : `product_${index}_${url || name}`,
    name,
    company: typeof product.company === "string" ? product.company : "",
    price: typeof product.price === "string" ? product.price : null,
    priceLabel,
    tags,
    url,
    platform: typeof product.platform === "string" ? product.platform : "",
    brief: typeof product.brief === "string" ? product.brief : "",
  };
}

function getLatestProducts(messages: ChatMessage[]): ProductCard[] {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const products = messages[i]?.products;
    if (products && products.length > 0) {
      return products;
    }
  }

  return [];
}

/**
 * 聊天主页面
 *
 * 整合所有组件，串联 SSE 流式链路：
 * 1. 用户输入消息 → 调用 /api/chat SSE
 * 2. 根据 SSE 事件实时更新消息列表与状态
 * 3. 支持推荐问题点击、错误重试、取消请求
 */
export default function ChatPageShell({
  backendMode = "legacy_chat",
  modeLabel,
  emptyTitle = "有什么保险问题想了解？",
  emptyDescription = "专业、客观、中立的AI保险咨询助手",
  fallbackSuggestions = DEFAULT_SUGGESTIONS,
}: ChatPageShellProps) {
  /** 消息列表 */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  /** 推荐问题 */
  const [suggestions, setSuggestions] = useState<string[]>([]);
  /** 推荐问题加载状态 */
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  /** 当前思考阶段 */
  const [thinkingStage, setThinkingStage] = useState<ThinkingStage | null>(null);
  /** 当前思考状态文案 */
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);
  /** 是否正在请求中 */
  const [isLoading, setIsLoading] = useState(false);
  /** 是否正在初始化匿名身份和会话 */
  const [isInitializing, setIsInitializing] = useState(true);
  /** 是否正在拉取历史消息 */
  const [historyLoading, setHistoryLoading] = useState(false);
  /** 初始化失败提示 */
  const [initError, setInitError] = useState<string | null>(null);
  /** 历史加载失败提示 */
  const [historyError, setHistoryError] = useState<string | null>(null);
  /** 当前推荐的产品列表（吸顶面板用） */
  const [currentProducts, setCurrentProducts] = useState<ProductCard[]>([]);
  /** 当前选中的产品（追问时自动关联） */
  const [selectedProduct, setSelectedProduct] = useState<{
    url: string;
    name: string;
  } | null>(null);
  /** 已完成 AI 解析的产品 URL，避免重复解析同一产品 */
  const [parsedProductUrls, setParsedProductUrls] = useState<Set<string>>(
    () => new Set(),
  );
  /** 用于取消请求的 AbortController */
  const abortRef = useRef<AbortController | null>(null);
  /** 记录上一次发送的消息，用于重试 */
  const lastMessageRef = useRef<string>("");
  /** 发送时读取最新会话，避免闭包拿到旧值 */
  const sessionRef = useRef<SessionIdentifiers | null>(null);
  /** 避免过期初始化流程覆盖新状态 */
  const initRunRef = useRef(0);

  /** 加载推荐问题 */
  useEffect(() => {
    fetchSuggestions()
      .then((items) => setSuggestions(items.length > 0 ? items : fallbackSuggestions))
      .catch(() => setSuggestions(fallbackSuggestions))
      .finally(() => setSuggestionsLoading(false));
  }, [fallbackSuggestions]);

  /** 初始化匿名身份、当前会话，并在后端支持时恢复历史 */
  const restoreCurrentSession = useCallback(async () => {
    const runId = initRunRef.current + 1;
    initRunRef.current = runId;
    const isActive = () => initRunRef.current === runId;

    setIsInitializing(true);
    setHistoryLoading(false);
    setInitError(null);
    setHistoryError(null);

    try {
      const anonymousId = await initializeAnonymousIdentity();
      let session = await initializeCurrentChatSession(anonymousId);
      let identifiers: SessionIdentifiers = {
        anonymousId,
        chatSessionId: session.chatSessionId,
      };

      if (!isActive()) return;
      sessionRef.current = identifiers;
      setMessages([]);
      setCurrentProducts([]);
      setSelectedProduct(null);

      if (isLocalChatSessionId(session.chatSessionId)) {
        return;
      }

      setHistoryLoading(true);
      try {
        const historyMessages = await fetchChatHistory(anonymousId, session.chatSessionId);
        if (!isActive()) return;
        setMessages(historyMessages);
        setCurrentProducts(getLatestProducts(historyMessages));
      } catch (err: unknown) {
        if (!isActive()) return;

        if (err instanceof ChatSessionNotFoundError) {
          clearCurrentChatSessionId();
          session = await startNewChatSession(anonymousId);
          identifiers = {
            anonymousId,
            chatSessionId: session.chatSessionId,
          };
          if (!isActive()) return;
          sessionRef.current = identifiers;
          setMessages([]);
          setCurrentProducts([]);
        } else {
          setHistoryError("历史消息加载失败，可刷新页面重试");
        }
      } finally {
        if (isActive()) {
          setHistoryLoading(false);
        }
      }
    } catch {
      if (!isActive()) return;
      sessionRef.current = null;
      setInitError("会话初始化失败，请刷新后重试");
    } finally {
      if (isActive()) {
        setIsInitializing(false);
      }
    }
  }, []);

  useEffect(() => {
    restoreCurrentSession();
  }, [restoreCurrentSession]);

  /** 更新助手消息（追加/修改最后一条助手消息） */
  const updateAssistantMessage = useCallback(
    (updater: (prev: ChatMessage) => ChatMessage) => {
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
          updated[lastIdx] = updater(updated[lastIdx]);
        }
        return updated;
      });
    },
    [],
  );

  const rememberBackendSessionId = useCallback((chatSessionId?: string) => {
    const normalizedChatSessionId = chatSessionId?.trim();
    const currentSession = sessionRef.current;

    if (
      !normalizedChatSessionId ||
      !currentSession ||
      currentSession.chatSessionId === normalizedChatSessionId
    ) {
      return;
    }

    sessionRef.current = {
      ...currentSession,
      chatSessionId: normalizedChatSessionId,
    };
    saveCurrentChatSessionId(normalizedChatSessionId);
  }, []);

  /** 发送消息核心逻辑 */
  const handleSend = useCallback(
    async (message: string) => {
      if (isLoading || isInitializing || historyLoading) return;

      const currentSession = sessionRef.current;
      if (!currentSession) {
        setInitError("会话尚未就绪，请刷新后重试");
        return;
      }

      // 保存消息用于重试
      lastMessageRef.current = message;

      // 取消上一个未完成的请求
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // 添加用户消息
      const userMsg: ChatMessage = {
        id: genId(),
        role: "user",
        content: message,
      };

      // 添加空的助手消息（用于流式填充）
      const assistantMsg: ChatMessage = {
        id: genId(),
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);
      setThinkingStage("analyzing");
      setThinkingMessage(null);

      // 对话开始后隐藏推荐问题
      setSuggestions([]);

      try {
        await sendChatMessage(
          message,
          {
            onStatus: (data) => {
              setThinkingStage(data.stage ?? null);
              setThinkingMessage(data.message ?? null);
            },
            onDelta: (data) => {
              setThinkingStage(null);
              setThinkingMessage(null);
              updateAssistantMessage((prev) => ({
                ...prev,
                content: prev.content + data.text,
              }));
            },
            onSources: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                sources: data.items,
              }));
            },
            onDisclaimer: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                disclaimer: data.text,
              }));
            },
            onDone: (data) => {
              rememberBackendSessionId(data.chat_session_id ?? data.sessionId);
              updateAssistantMessage((prev) => ({
                ...prev,
                isStreaming: false,
              }));
              setThinkingStage(null);
              setThinkingMessage(null);
              setIsLoading(false);
            },
            onProducts: (data) => {
              // RAG/Agent products 是主产品卡片来源，收到后立即更新吸顶面板。
              const items = (data.items as ProductEventItem[]).map(normalizeProductEventItem);
              setCurrentProducts(items);
              setSelectedProduct(null); // 新推荐到达时清空选中
            },
            onProductsUpdate: (data) => {
              setCurrentProducts((prevProducts) =>
                prevProducts.map((product) => {
                  const update = (data.items as Record<string, unknown>[]).find(
                    (item) => item.id === product.id
                  );
                  if (!update) return product;
                  return {
                    ...product,
                    price: (update.price as string) || product.price,
                    priceLabel:
                      (update.price_label as string) ||
                      (update.priceLabel as string) ||
                      (update.price as string) ||
                      product.priceLabel,
                    brief: (update.brief as string) || product.brief,
                  };
                }),
              );
              updateAssistantMessage((prev) => ({
                ...prev,
                products: (prev.products || []).map((p) => {
                  const update = (data.items as Record<string, unknown>[]).find(
                    (u) => u.id === p.id
                  );
                  if (!update) return p;
                  return {
                    ...p,
                    price: (update.price as string) || p.price,
                    priceLabel: (update.price_label as string) || (update.price as string) || p.priceLabel,
                    brief: (update.brief as string) || p.brief,
                  };
                }),
              }));
            },
            onError: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                isStreaming: false,
                error: data.message || "请求出错，请重试",
              }));
              setThinkingStage(null);
              setThinkingMessage(null);
              setIsLoading(false);
            },
          },
          {
            signal: controller.signal,
            anonymousId: currentSession.anonymousId,
            chatSessionId: currentSession.chatSessionId,
            backendMode,
            ...(selectedProduct ? {
              action: "product_followup",
              productUrl: selectedProduct.url,
              productName: selectedProduct.name,
            } : {}),
          },
        );
      } catch (err: unknown) {
        // 用户主动取消时不显示错误
        if (err instanceof Error && err.name === "AbortError") return;

        updateAssistantMessage((prev) => ({
          ...prev,
          isStreaming: false,
          error: "网络异常，请检查连接后重试",
        }));
        setThinkingStage(null);
        setThinkingMessage(null);
        setIsLoading(false);
      }
    },
    [
      updateAssistantMessage,
      rememberBackendSessionId,
      selectedProduct,
      backendMode,
      isLoading,
      isInitializing,
      historyLoading,
    ],
  );

  /** 重试上一次发送 */
  const handleRetry = useCallback(() => {
    if (!lastMessageRef.current) return;
    // 移除最后一条出错的助手消息
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.error) {
        return prev.slice(0, -1);
      }
      return prev;
    });
    handleSend(lastMessageRef.current);
  }, [handleSend]);

  /** 点击推荐问题 */
  const handleSuggestionSelect = useCallback(
    (question: string) => {
      handleSend(question);
    },
    [handleSend],
  );

  /** 点击"查看保障详情"按钮 */
  const handleViewDetail = useCallback(
    async (productUrl: string, productName: string) => {
      if (isLoading || isInitializing || historyLoading) return;
      if (parsedProductUrls.has(productUrl)) {
        setSelectedProduct({ url: productUrl, name: productName });
        return;
      }

      const currentSession = sessionRef.current;
      if (!currentSession) {
        setInitError("会话尚未就绪，请刷新后重试");
        return;
      }

      setSelectedProduct({ url: productUrl, name: productName });
      // 取消上一个未完成的请求
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // 添加空的助手消息
      const assistantMsg: ChatMessage = {
        id: genId(),
        role: "assistant",
        content: "",
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoading(true);
      setThinkingStage("reading");
      setThinkingMessage(null);

      try {
        await sendChatMessage(
          "",
          {
            onStatus: (data) => {
              setThinkingStage(data.stage ?? null);
              setThinkingMessage(data.message ?? null);
            },
            onDetailItems: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                duties: data.duties,
                detailProductName: data.product_name,
              }));
            },
            onDelta: (data) => {
              setThinkingStage(null);
              setThinkingMessage(null);
              updateAssistantMessage((prev) => ({
                ...prev,
                content: prev.content + data.text,
              }));
            },
            onDone: (data) => {
              rememberBackendSessionId(data.chat_session_id ?? data.sessionId);
              updateAssistantMessage((prev) => ({
                ...prev,
                isStreaming: false,
              }));
              setParsedProductUrls((prev) => {
                if (prev.has(productUrl)) return prev;
                const next = new Set(prev);
                next.add(productUrl);
                return next;
              });
              setThinkingStage(null);
              setThinkingMessage(null);
              setIsLoading(false);
            },
            onError: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                isStreaming: false,
                error: data.message || "请求出错，请重试",
              }));
              setThinkingStage(null);
              setThinkingMessage(null);
              setIsLoading(false);
            },
          },
          {
            signal: controller.signal,
            anonymousId: currentSession.anonymousId,
            chatSessionId: currentSession.chatSessionId,
            backendMode,
            action: "product_detail",
            productUrl,
            productName,
          },
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        updateAssistantMessage((prev) => ({
          ...prev,
          isStreaming: false,
          error: "网络异常，请检查连接后重试",
        }));
        setThinkingStage(null);
        setThinkingMessage(null);
        setIsLoading(false);
      }
    },
    [
      updateAssistantMessage,
      rememberBackendSessionId,
      parsedProductUrls,
      backendMode,
      isLoading,
      isInitializing,
      historyLoading,
    ],
  );

  /** 新建聊天会话 */
  const handleNewChat = useCallback(async () => {
    if (isLoading || isInitializing || historyLoading) return;

    setIsInitializing(true);
    setInitError(null);
    setHistoryError(null);
    abortRef.current?.abort();

    try {
      const anonymousId = sessionRef.current?.anonymousId ?? await initializeAnonymousIdentity();
      const session = await startNewChatSession(anonymousId);
      const identifiers: SessionIdentifiers = {
        anonymousId,
        chatSessionId: session.chatSessionId,
      };

      sessionRef.current = identifiers;
      setMessages([]);
      setCurrentProducts([]);
      setSelectedProduct(null);
      setParsedProductUrls(new Set());
      setThinkingStage(null);
      setThinkingMessage(null);
      lastMessageRef.current = "";
    } catch {
      setInitError("新建会话失败，请稍后重试");
    } finally {
      setIsInitializing(false);
    }
  }, [isLoading, isInitializing, historyLoading]);

  /** 选中/取消选中产品 */
  const handleSelectProduct = useCallback((url: string, name: string) => {
    setSelectedProduct((prev) =>
      prev?.url === url ? null : { url, name }
    );
  }, []);

  const handleAnalyzeSelectedProduct = useCallback(() => {
    if (!selectedProduct) return;
    handleViewDetail(selectedProduct.url, selectedProduct.name);
  }, [selectedProduct, handleViewDetail]);

  /** 是否显示推荐问题区域（仅在没有消息且非加载状态时） */
  const isSessionBusy = isInitializing || historyLoading;
  const showSuggestions = messages.length === 0 && !isSessionBusy && !initError;
  const inputDisabled = isLoading || isSessionBusy || Boolean(initError);
  const selectedProductAnalyzed = selectedProduct
    ? parsedProductUrls.has(selectedProduct.url)
    : false;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-gray-50">
      {/* 页面标题 */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-3 py-2.5 sm:px-4 sm:py-3">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="min-w-0 text-base font-semibold text-gray-800 sm:text-lg">
              AI 智能保险顾问
            </h1>
            {modeLabel && (
              <span className="shrink-0 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 sm:text-xs">
                {modeLabel}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleNewChat}
            disabled={inputDisabled}
            className="shrink-0 rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50 sm:px-3 sm:text-sm"
          >
            新建聊天
          </button>
        </div>
      </header>

      {/* 消息区域 */}
      <main
        className={`flex flex-1 flex-col overflow-hidden ${
          selectedProduct
            ? "pb-[calc(156px+env(safe-area-inset-bottom))] sm:pb-36"
            : "pb-[calc(88px+env(safe-area-inset-bottom))] sm:pb-20"
        }`}
      >
        {initError ? (
          <div className="flex flex-1 flex-col items-center justify-center px-4 text-center">
            <p className="mb-4 text-sm text-red-600">{initError}</p>
            <button
              type="button"
              onClick={restoreCurrentSession}
              className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-600 transition-colors hover:bg-red-100"
            >
              重试
            </button>
          </div>
        ) : isSessionBusy ? (
          <div className="flex flex-1 items-center justify-center px-4 text-sm text-gray-500">
            {isInitializing ? "正在初始化会话..." : "正在恢复历史消息..."}
          </div>
        ) : showSuggestions ? (
          /* 首页：推荐问题 */
          <div className="flex flex-1 flex-col items-center justify-start px-3 pt-12 sm:justify-center sm:px-0 sm:pt-0">
            <h2 className="mb-2 text-center text-lg font-medium text-gray-700 sm:text-xl">
              {emptyTitle}
            </h2>
            <p className="mb-4 text-center text-sm text-gray-400 sm:mb-6">
              {emptyDescription}
            </p>
            <SuggestionList
              suggestions={suggestions}
              onSelect={handleSuggestionSelect}
              loading={suggestionsLoading}
            />
            {historyError && (
              <p className="mt-3 px-4 text-center text-xs text-amber-600">
                {historyError}
              </p>
            )}
          </div>
        ) : (
          /* 对话中：消息列表 */
          <>
            {/* 产品吸顶面板 */}
            <ProductPanel
              products={currentProducts}
              selectedUrl={selectedProduct?.url ?? null}
              onSelect={handleSelectProduct}
            />

            <ChatMessageList messages={messages} onViewDetail={handleViewDetail} />

            {historyError && (
              <div className="mx-auto w-full max-w-3xl px-4 py-2 text-xs text-amber-600">
                {historyError}
              </div>
            )}

            {/* 思考状态提示 */}
            {(thinkingStage || thinkingMessage) && (
              <div className="mx-auto w-full max-w-3xl px-4 py-2">
                <ThinkingStatus stage={thinkingStage} message={thinkingMessage} />
              </div>
            )}

            {/* 错误重试按钮 */}
            {!isLoading &&
              messages.length > 0 &&
              messages[messages.length - 1]?.error && (
                <div className="mx-auto w-full max-w-3xl px-4 py-2">
                  <button
                    type="button"
                    onClick={handleRetry}
                    className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-600 transition-colors hover:bg-red-100"
                  >
                    重新发送
                  </button>
                </div>
              )}
          </>
        )}
      </main>

      {/* 底部输入区 */}
      <ChatInput
        onSend={handleSend}
        disabled={inputDisabled}
        selectedProduct={selectedProduct}
        selectedProductAnalyzed={selectedProductAnalyzed}
        onAnalyzeSelectedProduct={handleAnalyzeSelectedProduct}
      />
    </div>
  );
}
