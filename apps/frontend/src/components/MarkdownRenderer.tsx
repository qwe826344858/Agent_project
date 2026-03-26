"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

/**
 * Markdown 渲染组件
 * - 支持 GFM（表格、删除线、任务列表）
 * - 流式输出时在末尾显示闪烁蓝色方块光标
 * - 新段落出现时有淡入上滑动效
 */
export default function MarkdownRenderer({
  content,
  isStreaming,
}: MarkdownRendererProps) {
  return (
    <div className="markdown-body text-gray-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      {isStreaming && <span className="streaming-cursor" aria-label="正在输入" />}
    </div>
  );
}
