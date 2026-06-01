"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ProductCard } from "@/types/chat";

interface ProductPanelProps {
  products: ProductCard[];
  selectedUrl: string | null;
  onSelect: (url: string, name: string) => void;
}

/**
 * 产品吸顶面板 — 固定在消息流上方，始终可见
 * 视觉保持与旧版产品推荐卡片一致：盾牌图标、产品信息、标签、价格简介区、底部查看按钮。
 */
export default function ProductPanel({
  products,
  selectedUrl,
  onSelect,
}: ProductPanelProps) {
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const selectedIndex = products.findIndex((product) => product.url === selectedUrl);
    if (selectedIndex >= 0) {
      setActiveIndex(selectedIndex);
      return;
    }

    setActiveIndex((prev) => Math.min(prev, Math.max(products.length - 1, 0)));
  }, [products, selectedUrl]);

  const selectProductAt = useCallback(
    (index: number) => {
      if (products.length === 0) return;

      const nextIndex = (index + products.length) % products.length;
      const product = products[nextIndex];
      setActiveIndex(nextIndex);
      onSelect(product.url, product.name);
      window.requestAnimationFrame(() => {
        cardRefs.current[nextIndex]?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "center",
        });
      });
    },
    [onSelect, products],
  );

  if (!products || products.length === 0) return null;

  return (
    <div className="shrink-0 border-b border-gray-100 bg-white/95 px-3 py-2 backdrop-blur-sm sm:px-4 sm:py-4">
      <div className="mb-2 flex items-center justify-between gap-2 sm:mb-3">
        <span className="min-w-0 flex-1 truncate text-xs text-gray-500 sm:text-sm">
          为您找到 <strong className="text-gray-700">{products.length}</strong> 款相关产品
          {selectedUrl && <span className="ml-2 text-blue-500">· 已选中 1 款</span>}
        </span>

        {products.length > 1 && (
          <div className="flex shrink-0 items-center gap-1 sm:hidden">
            <button
              type="button"
              aria-label="上一款产品"
              className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-white text-lg leading-none text-gray-600 shadow-sm active:bg-gray-100"
              onClick={() => selectProductAt(activeIndex - 1)}
            >
              ‹
            </button>
            <span className="w-9 text-center text-[11px] text-gray-400">
              {activeIndex + 1}/{products.length}
            </span>
            <button
              type="button"
              aria-label="下一款产品"
              className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-white text-lg leading-none text-gray-600 shadow-sm active:bg-gray-100"
              onClick={() => selectProductAt(activeIndex + 1)}
            >
              ›
            </button>
          </div>
        )}
      </div>

      <div className="product-list-wrapper">
        <div className="product-scroll flex snap-x snap-mandatory gap-2.5 overflow-x-auto scroll-px-3 pb-1 sm:gap-3 sm:scroll-px-0 sm:pb-2">
          {products.map((product, index) => {
            const isSelected = selectedUrl === product.url;
            const visibleTags = product.tags.slice(0, 4);
            const summary =
              product.brief ||
              "可关注保障责任、投保条件、续保规则、免赔额和赔付比例等核心条款。";
            return (
              <div
                key={product.id}
                ref={(node) => {
                  cardRefs.current[index] = node;
                }}
                className="product-card product-card-enter relative flex min-h-[184px] w-[78vw] max-w-[276px] shrink-0 snap-center cursor-pointer flex-col sm:min-h-[264px] sm:w-[320px] sm:max-w-[320px]"
                style={{
                  borderColor: isSelected ? "#3b82f6" : undefined,
                  boxShadow: isSelected
                    ? "0 0 0 1px rgba(59, 130, 246, 0.35), 0 8px 25px rgba(59, 130, 246, 0.12), 0 4px 10px rgba(0, 0, 0, 0.06)"
                    : undefined,
                }}
                onClick={() => {
                  setActiveIndex(index);
                  onSelect(product.url, product.name);
                }}
              >
                <div className="p-2.5 pb-0 sm:p-4 sm:pb-0">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 text-lg leading-none sm:text-xl">🛡️</span>
                    <div className="min-w-0 flex-1">
                      <h3 className="line-clamp-1 text-sm font-semibold leading-snug text-gray-800 sm:line-clamp-2">
                        {product.name}
                      </h3>
                      <p className="mt-0.5 truncate text-xs text-gray-400">
                        {product.company || "保险公司"} · {product.platform || "投保平台"}
                      </p>
                    </div>
                  </div>

                  {visibleTags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1 sm:mt-2.5 sm:gap-1.5">
                      {visibleTags.map((tag, tagIndex) => (
                        <span
                          key={tag}
                          className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[11px] font-medium sm:px-2 sm:text-xs ${
                            tagIndex > 2 ? "hidden sm:inline-flex " : ""
                          }${
                            tag.includes("少儿")
                              ? "bg-pink-50 text-pink-600"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="price-section mx-2.5 mt-2 sm:mx-4 sm:mt-3">
                  <div className="truncate text-sm font-bold text-green-600 sm:text-lg">
                    💰 {product.price || product.priceLabel || "价格待确认"}
                  </div>
                  <p className="mt-1 line-clamp-1 text-xs leading-5 text-gray-500 sm:line-clamp-2">
                    {summary}
                  </p>
                </div>

                <div className="mt-auto p-2.5 pt-2 sm:p-4 sm:pt-3">
                  <a
                    href={product.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full rounded-lg bg-blue-500 py-1.5 text-center text-xs font-medium text-white transition-colors duration-200 hover:bg-blue-600 active:bg-blue-700 sm:py-2 sm:text-sm"
                    onClick={(e) => e.stopPropagation()}
                  >
                    查看详情 <span className="ml-0.5">→</span>
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
