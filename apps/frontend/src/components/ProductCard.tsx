"use client";

import { ProductCard as ProductCardType } from "@/types/chat";

/** 标签颜色映射 */
const TAG_COLORS: Record<string, { bg: string; text: string }> = {
  百万医疗: { bg: "bg-blue-50", text: "text-blue-600" },
  医疗险: { bg: "bg-blue-50", text: "text-blue-600" },
  重疾险: { bg: "bg-purple-50", text: "text-purple-600" },
  重大疾病: { bg: "bg-purple-50", text: "text-purple-600" },
  意外险: { bg: "bg-orange-50", text: "text-orange-600" },
  意外保障: { bg: "bg-orange-50", text: "text-orange-600" },
  寿险: { bg: "bg-rose-50", text: "text-rose-600" },
  定期寿险: { bg: "bg-rose-50", text: "text-rose-600" },
  保证续保: { bg: "bg-green-50", text: "text-green-600" },
  免赔额: { bg: "bg-yellow-50", text: "text-yellow-700" },
  少儿: { bg: "bg-pink-50", text: "text-pink-600" },
  养老: { bg: "bg-teal-50", text: "text-teal-600" },
};
const DEFAULT_TAG = { bg: "bg-gray-50", text: "text-gray-600" };

/** 根据标签内容匹配颜色 */
function getTagColor(tag: string) {
  for (const [keyword, color] of Object.entries(TAG_COLORS)) {
    if (tag.includes(keyword)) return color;
  }
  return DEFAULT_TAG;
}

interface ProductCardProps {
  product: ProductCardType;
  index: number;
}

/**
 * 单张产品推荐卡片
 * - 入场交错动效（由 index 控制延迟）
 * - 价格高亮区 + shimmer 骨架屏
 * - 标签自动分色
 * - 悬浮上移 + 按下微缩反馈
 * - 全宽 CTA 按钮
 */
export default function ProductCard({ product, index }: ProductCardProps) {
  return (
    <div
      className="product-card product-card-enter min-w-[260px] max-w-[320px] shrink-0 flex flex-col"
      style={{ animationDelay: `${index * 120}ms` }}
    >
      {/* 产品名称 + 公司信息 */}
      <div className="p-4 pb-0">
        <div className="flex items-start gap-2">
          <span className="text-xl leading-none mt-0.5">🛡️</span>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-800 leading-snug line-clamp-2">
              {product.name}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {product.company} · {product.platform}
            </p>
          </div>
        </div>

        {/* 标签区域 */}
        {product.tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {product.tags.map((tag) => {
              const color = getTagColor(tag);
              return (
                <span
                  key={tag}
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color.bg} ${color.text}`}
                >
                  {tag}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* 价格高亮区 */}
      <div className="mx-4 mt-3 price-section">
        {product.price !== null ? (
          <>
            <div className="text-lg font-bold text-green-600">
              💰 {product.price}
            </div>
            {product.brief && (
              <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                {product.brief}
              </p>
            )}
          </>
        ) : (
          <div className="flex items-center gap-2">
            <div className="price-skeleton" />
            <span className="text-xs text-gray-400">
              {product.priceLabel || "加载中"}
            </span>
          </div>
        )}
      </div>

      {/* CTA 按钮 */}
      <div className="p-4 pt-3 mt-auto">
        <a
          href={product.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-2 bg-blue-500 hover:bg-blue-600 active:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          查看详情 <span className="ml-0.5">→</span>
        </a>
      </div>
    </div>
  );
}
