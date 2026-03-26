"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { ChatMessage, SourceItem } from "@/types/chat";
import ProductCardList from "@/components/ProductCardList";
import MarkdownRenderer from "@/components/MarkdownRenderer";

interface ChatMessageListProps {
  messages: ChatMessage[];
}

/**
 * 聊天消息列表组件
 * - 渲染用户和助手的消息气泡
 * - 助手消息使用 MarkdownRenderer 渲染流式文本
 * - 自动滚动：节流 + 用户手动上滚暂停
 */
export default function ChatMessageList({ messages }: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollThrottleRef = useRef<number>(0);
  const [userScrolled, setUserScrolled] = useState(false);

  /** 节流滚动到底部（每 100ms 最多一次） */
  const scrollToBottom = useCallback(() => {
    const now = Date.now();
    if (now - scrollThrottleRef.current < 100) return;
    scrollThrottleRef.current = now;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  /** 检测用户是否手动上滚 */
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setUserScrolled(!atBottom);
  }, []);

  /** 仅在未手动上滚时自动跟随 */
  useEffect(() => {
    if (!userScrolled) {
      scrollToBottom();
    }
  }, [messages, userScrolled, scrollToBottom]);

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-4"
      onScroll={handleScroll}
    >
      {messages.map((msg) => (
        <div key={msg.id}>
          {msg.role === "user" ? (
            <UserBubble message={msg} />
          ) : (
            <AssistantBubble message={msg} />
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

/** 用户消息气泡 */
function UserBubble({ message }: { message: ChatMessage }) {
  const hasError = !!message.error;

  return (
    <div className="flex justify-end">
      <div
        className={`ml-auto rounded-2xl px-4 py-2 max-w-[80%] ${
          hasError
            ? "bg-red-50 border-2 border-red-400 text-red-700"
            : "bg-blue-500 text-white"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {hasError && (
          <p className="mt-1 text-xs text-red-500">{message.error}</p>
        )}
      </div>
    </div>
  );
}

/** 助手消息气泡，包含产品卡片、Markdown 文本、来源和免责声明 */
function AssistantBubble({ message }: { message: ChatMessage }) {
  const hasError = !!message.error;
  const hasSources = message.sources && message.sources.length > 0;
  const hasDisclaimer = !!message.disclaimer;
  const hasProducts = message.products && message.products.length > 0;

  return (
    <div className="flex flex-col items-start">
      {/* 产品推荐卡片（在文字回答之前展示） */}
      {hasProducts && (
        <div className="mr-auto max-w-[95%] mb-2">
          <ProductCardList products={message.products!} />
        </div>
      )}

      {/* 消息气泡 — 使用 MarkdownRenderer */}
      <div
        className={`mr-auto rounded-2xl px-4 py-3 max-w-[85%] overflow-x-auto ${
          hasError
            ? "bg-red-50 border-2 border-red-400 text-red-700"
            : "bg-white border border-gray-200"
        }`}
      >
        {(message.content || message.isStreaming) && (
          <MarkdownRenderer
            content={message.content}
            isStreaming={message.isStreaming}
          />
        )}
        {hasError && (
          <p className="mt-1 text-xs text-red-500">{message.error}</p>
        )}
      </div>

      {/* 来源列表 */}
      {hasSources && (
        <div className="mt-2 ml-1 max-w-[80%]">
          <p className="text-xs text-gray-500 mb-1">来源：</p>
          <ul className="space-y-0.5">
            {message.sources!.map((source: SourceItem, index: number) => (
              <li key={index} className="text-xs text-gray-400">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-600 hover:underline"
                >
                  {source.title}
                </a>
                <span className="ml-1 text-gray-300">— {source.site}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 免责声明 */}
      {hasDisclaimer && (
        <p className="mt-1 ml-1 max-w-[80%] text-[11px] text-gray-400 italic">
          {message.disclaimer}
        </p>
      )}
    </div>
  );
}
