"use client";

import { ProductCard } from "@/types/chat";

interface ProductPanelProps {
  products: ProductCard[];
  selectedUrl: string | null;
  onSelect: (url: string, name: string) => void;
  onViewDetail: (url: string, name: string) => void;
}

/**
 * 产品吸顶面板 — 固定在消息流上方，始终可见
 * - 精简卡片：名称 + 价格 + 平台
 * - 选中态：蓝色边框 + "已选中"标记
 * - 横向滚动 + 渐变遮罩
 */
export default function ProductPanel({ products, selectedUrl, onSelect, onViewDetail }: ProductPanelProps) {
  if (!products || products.length === 0) return null;

  return (
    <div className="shrink-0 border-b border-gray-100 bg-white/95 backdrop-blur-sm px-4 py-3">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">
          为您找到 <strong className="text-gray-700">{products.length}</strong> 款相关产品
          {selectedUrl && <span className="ml-2 text-blue-500">· 已选中 1 款</span>}
        </span>
      </div>

      {/* 卡片滚动区域 */}
      <div className="product-list-wrapper">
        <div className="product-scroll flex gap-2.5 overflow-x-auto pb-1">
          {products.map((product) => {
            const isSelected = selectedUrl === product.url;
            return (
              <div
                key={product.id}
                className={`relative shrink-0 min-w-[200px] max-w-[240px] rounded-lg border p-3 cursor-pointer transition-all duration-200
                  ${isSelected
                    ? "border-blue-400 bg-blue-50/50 ring-1 ring-blue-400"
                    : "border-gray-200 bg-white hover:border-blue-200 hover:shadow-sm"
                  }`}
                onClick={() => onSelect(product.url, product.name)}
              >
                {/* 选中标记 */}
                {isSelected && (
                  <span className="absolute -top-1.5 -right-1.5 bg-blue-500 text-white text-[10px] rounded-full w-5 h-5 flex items-center justify-center">
                    ✓
                  </span>
                )}

                {/* 产品名 */}
                <h4 className="text-xs font-semibold text-gray-800 line-clamp-1 mb-1">
                  {product.name}
                </h4>

                {/* 价格 + 平台 */}
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-green-600">
                    {product.price || "查看详情"}
                  </span>
                  <span className="text-gray-400">{product.platform}</span>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-1.5 mt-2">
                  <a
                    href={product.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 text-center py-1 text-[11px] text-gray-500 hover:text-blue-500 border border-gray-200 rounded transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    投保页面
                  </a>
                  <button
                    type="button"
                    className={`flex-1 text-center py-1 text-[11px] rounded transition-colors
                      ${isSelected
                        ? "bg-blue-500 text-white"
                        : "text-blue-500 border border-blue-200 hover:bg-blue-50"
                      }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewDetail(product.url, product.name);
                    }}
                  >
                    {isSelected ? "✓ 已解析" : "AI解析保障"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
