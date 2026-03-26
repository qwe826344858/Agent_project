"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { ProductCard as ProductCardType } from "@/types/chat";
import ProductCard from "@/components/ProductCard";

interface ProductCardListProps {
  products: ProductCardType[];
}

/**
 * 产品推荐卡片列表容器
 * - 横向滚动布局 + 渐变遮罩指示
 * - 数量徽标
 * - 滚动条美化
 * - 空结果友好提示
 */
export default function ProductCardList({ products }: ProductCardListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrolledEnd, setScrolledEnd] = useState(false);
  const [showFade, setShowFade] = useState(false);

  /** 检测是否需要显示渐变遮罩 */
  const checkOverflow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const hasOverflow = el.scrollWidth > el.clientWidth + 10;
    setShowFade(hasOverflow);
    if (!hasOverflow) setScrolledEnd(false);
  }, []);

  /** 滚动位置检测 */
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 10;
    setScrolledEnd(atEnd);
  }, []);

  /** 初始化 + 产品变化时重新检测溢出 */
  useEffect(() => {
    checkOverflow();
    // ResizeObserver 监听容器尺寸变化
    const el = scrollRef.current;
    if (!el) return;
    const observer = new ResizeObserver(checkOverflow);
    observer.observe(el);
    return () => observer.disconnect();
  }, [products, checkOverflow]);

  if (products.length === 0) return null;

  return (
    <div className="space-y-2">
      {/* 数量徽标 */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span className="inline-flex items-center gap-1">
          为您找到 <strong className="text-gray-700">{products.length}</strong> 款相关产品
        </span>
      </div>

      {/* 卡片滚动区域 */}
      <div className={`product-list-wrapper ${showFade && !scrolledEnd ? "" : "scrolled-end"}`}>
        <div
          ref={scrollRef}
          className="product-scroll flex gap-3 overflow-x-auto pb-2"
          onScroll={handleScroll}
        >
          {products.map((product, index) => (
            <ProductCard key={product.id} product={product} index={index} />
          ))}
        </div>
      </div>
    </div>
  );
}
