"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage, ThinkingStage, ProductCard } from "@/types/chat";
import { sendChatMessage, fetchSuggestions } from "@/lib/api";
import ChatInput from "@/components/ChatInput";
import ChatMessageList from "@/components/ChatMessageList";
import ThinkingStatus from "@/components/ThinkingStatus";
import SuggestionList from "@/components/SuggestionList";

/** 生成唯一消息 ID */
function genId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * 聊天主页面
 *
 * 整合所有组件，串联 SSE 流式链路：
 * 1. 用户输入消息 → 调用 /api/chat SSE
 * 2. 根据 SSE 事件实时更新消息列表与状态
 * 3. 支持推荐问题点击、错误重试、取消请求
 */
export default function ChatPage() {
  /** 消息列表 */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  /** 推荐问题 */
  const [suggestions, setSuggestions] = useState<string[]>([]);
  /** 推荐问题加载状态 */
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  /** 当前思考阶段 */
  const [thinkingStage, setThinkingStage] = useState<ThinkingStage | null>(null);
  /** 是否正在请求中 */
  const [isLoading, setIsLoading] = useState(false);
  /** 用于取消请求的 AbortController */
  const abortRef = useRef<AbortController | null>(null);
  /** 记录上一次发送的消息，用于重试 */
  const lastMessageRef = useRef<string>("");

  /** 加载推荐问题 */
  useEffect(() => {
    fetchSuggestions()
      .then(setSuggestions)
      .catch(() => setSuggestions([]))
      .finally(() => setSuggestionsLoading(false));
  }, []);

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

  /** 发送消息核心逻辑 */
  const handleSend = useCallback(
    async (message: string) => {
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

      // 对话开始后隐藏推荐问题
      setSuggestions([]);

      try {
        await sendChatMessage(
          message,
          {
            onStatus: (data) => {
              setThinkingStage(data.stage as ThinkingStage);
            },
            onDelta: (data) => {
              setThinkingStage(null);
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
            onDone: () => {
              updateAssistantMessage((prev) => ({
                ...prev,
                isStreaming: false,
              }));
              setThinkingStage(null);
              setIsLoading(false);
            },
            onProducts: (data) => {
              updateAssistantMessage((prev) => ({
                ...prev,
                products: (data.items as (ProductCard & { price_label?: string })[]).map((p) => ({
                  ...p,
                  priceLabel: p.price_label || p.priceLabel || "加载中",
                })),
              }));
            },
            onProductsUpdate: (data) => {
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
              setIsLoading(false);
            },
          },
          { signal: controller.signal },
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
        setIsLoading(false);
      }
    },
    [updateAssistantMessage],
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

  /** 是否显示推荐问题区域（仅在没有消息且非加载状态时） */
  const showSuggestions = messages.length === 0;

  return (
    <div className="flex h-screen flex-col">
      {/* 页面标题 */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-4 py-3">
        <h1 className="mx-auto max-w-3xl text-lg font-semibold text-gray-800">
          AI 智能保险顾问
        </h1>
      </header>

      {/* 消息区域 */}
      <main className="flex flex-1 flex-col overflow-hidden pb-20">
        {showSuggestions ? (
          /* 首页：推荐问题 */
          <div className="flex flex-1 flex-col items-center justify-center">
            <h2 className="mb-2 text-xl font-medium text-gray-700">
              有什么保险问题想了解？
            </h2>
            <p className="mb-6 text-sm text-gray-400">
              专业、客观、中立的AI保险咨询助手
            </p>
            <SuggestionList
              suggestions={suggestions}
              onSelect={handleSuggestionSelect}
              loading={suggestionsLoading}
            />
          </div>
        ) : (
          /* 对话中：消息列表 */
          <>
            <ChatMessageList messages={messages} />

            {/* 思考状态提示 */}
            {thinkingStage && (
              <div className="mx-auto w-full max-w-3xl px-4 py-2">
                <ThinkingStatus stage={thinkingStage} />
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
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
