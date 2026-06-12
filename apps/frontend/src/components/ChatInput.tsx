"use client";

import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from "react";

/** ChatInput 组件的 Props 类型 */
interface ChatInputProps {
  /** 发送消息的回调函数 */
  onSend: (message: string) => void;
  /** 是否禁用输入（如请求进行中时禁止重复发送） */
  disabled?: boolean;
  /** 当前选中的产品 */
  selectedProduct?: {
    url: string;
    name: string;
  } | null;
  /** 选中产品是否已经完成 AI 解析 */
  selectedProductAnalyzed?: boolean;
  /** 触发当前选中产品的 AI 解析 */
  onAnalyzeSelectedProduct?: () => void;
}

/**
 * 聊天输入组件
 * - 包含多行文本框和发送按钮
 * - 回车发送，Shift+Enter 换行
 * - 输入为空或 disabled 时禁止发送
 * - 固定在页面底部，适配移动端
 */
export default function ChatInput({
  onSend,
  disabled = false,
  selectedProduct = null,
  selectedProductAnalyzed = false,
  onAnalyzeSelectedProduct,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /** 判断当前是否可以发送 */
  const canSend = message.trim().length > 0 && !disabled;

  /** 发送消息并清空输入框 */
  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setMessage("");

    // 重置 textarea 高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [message, disabled, onSend]);

  /** 键盘事件：Enter 发送，Shift+Enter 换行 */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  /** 输入内容变化时自动调整高度 */
  const handleChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);

    // 自动调整 textarea 高度，最大不超过 160px
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-10 border-t border-gray-200 bg-white px-3 py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] sm:px-4 sm:py-3 sm:pb-3">
      <div className="mx-auto max-w-3xl space-y-2">
        {selectedProduct && (
          <div className="flex flex-col items-stretch gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-gray-500">已选产品</p>
              <p className="truncate text-sm font-medium text-gray-800">
                {selectedProduct.name}
              </p>
            </div>
            <button
              type="button"
              onClick={onAnalyzeSelectedProduct}
              disabled={disabled || selectedProductAnalyzed || !onAnalyzeSelectedProduct}
              className="w-full shrink-0 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 active:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500 sm:w-auto"
            >
              {selectedProductAnalyzed ? "已完成解析" : "AI解析保障"}
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 sm:gap-3">
          {/* 多行文本输入框 */}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="输入你的问题…"
            rows={1}
            className="min-h-11 flex-1 resize-none rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm leading-6 placeholder-gray-400 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 sm:px-4 sm:text-base"
          />

          {/* 发送按钮 */}
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            className="min-h-11 shrink-0 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 active:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-500 sm:px-5"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
