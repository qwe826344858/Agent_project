"use client";

import { ThinkingStage } from "@/types/chat";

/** 组件属性 */
interface ThinkingStatusProps {
  stage: ThinkingStage | null;
}

/** stage 到中文文案的映射 */
const stageTextMap: Record<ThinkingStage, string> = {
  analyzing: "正在分析您的问题...",
  searching: "正在搜索保险产品...",
  reading: "正在整理搜索结果...",
  answering: "正在生成选购建议，您可以先浏览上方产品...",
};

/**
 * 思考状态提示组件
 * 根据当前 stage 显示对应的中文状态文案，并附带跳动圆点加载动画。
 * stage 为 null 或 undefined 时不渲染任何内容。
 */
export default function ThinkingStatus({ stage }: ThinkingStatusProps) {
  // stage 为空时不渲染
  if (!stage) return null;

  const text = stageTextMap[stage];

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
