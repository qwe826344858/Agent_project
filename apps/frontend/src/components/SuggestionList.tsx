"use client";

interface SuggestionListProps {
  /** 推荐问题列表 */
  suggestions: string[];
  /** 用户点击某条推荐问题后的回调，参数为问题文本 */
  onSelect: (question: string) => void;
  /** 是否正在加载推荐问题 */
  loading?: boolean;
}

/**
 * 推荐问题列表组件
 * - 展示 3~5 条推荐问题，供用户快速选择
 * - 每条推荐问题为可点击卡片，点击后通过 onSelect 回调传递给父组件
 * - 支持 loading 骨架屏状态
 * - 列表为空且非加载状态时不渲染任何内容
 */
export default function SuggestionList({
  suggestions,
  onSelect,
  loading = false,
}: SuggestionListProps) {
  /* 非加载状态下，列表为空则不渲染 */
  if (!loading && suggestions.length === 0) {
    return null;
  }

  return (
    <div className="mx-auto w-full max-w-2xl py-6 px-4">
      {/* 引导文案 */}
      <p className="mb-3 text-center text-sm text-gray-500">
        您可以试试问我
      </p>

      {/* 骨架屏：加载中显示脉冲动画占位 */}
      {loading ? (
        <div className="space-y-3" aria-label="加载推荐问题中">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-12 rounded-xl bg-gray-200 animate-pulse"
            />
          ))}
        </div>
      ) : (
        /* 推荐问题卡片列表 */
        <ul className="space-y-3">
          {suggestions.map((question, index) => (
            <li key={index}>
              <button
                type="button"
                onClick={() => onSelect(question)}
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-600 transition-colors hover:border-blue-300 hover:bg-blue-50 cursor-pointer"
              >
                {question}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
