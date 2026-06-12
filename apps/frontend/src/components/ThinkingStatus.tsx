"use client";

import type { ThinkingStage } from "@/types/chat";

/** 组件属性 */
interface ThinkingStatusProps {
  stage: ThinkingStage | null;
  message?: string | null;
}

/** stage 到中文文案的映射 */
const stageTextMap: Record<string, string> = {
  analyzing: "正在分析您的问题...",
  searching: "正在搜索保险产品...",
  reading: "正在整理搜索结果...",
  answering: "正在生成选购建议，您可以先浏览上方产品...",
  reasoning: "正在规划下一步...",
  planning: "正在规划下一步...",
  tool_running: "正在调用工具...",
  tool_calling: "正在调用工具...",
  selecting_tool: "正在选择工具...",
};

/**
 * 思考状态提示组件
 * 根据当前 stage 显示对应的中文状态文案，并附带跳动圆点加载动画。
 * stage 和 message 都为空时不渲染任何内容。
 */
export default function ThinkingStatus({ stage, message }: ThinkingStatusProps) {
  // stage 和 message 都为空时不渲染
  if (!stage && !message) return null;

  const text = message?.trim() || (stage ? stageTextMap[stage] || stage : "");

  return (
    <div className="flex items-center gap-2 text-gray-500 text-sm">
      {/* 跳动圆点动画 */}
      <span className="flex items-center gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-[thinking-bounce_0.6s_ease-in-out_infinite_alternate]"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </span>
      <span>{text}</span>
    </div>
  );
}
