"use client";

import { DutyItem } from "@/types/chat";

interface DutyDetailCardProps {
  productName: string;
  duties: DutyItem[];
}

/**
 * 产品保障详情卡片
 * - 展示保障项列表（名称/额度/必选or可选）
 * - 必选项用蓝色标签，可选项用灰色标签
 */
export default function DutyDetailCard({ productName, duties }: DutyDetailCardProps) {
  if (!duties || duties.length === 0) return null;

  return (
    <div className="w-full max-w-none rounded-lg border border-blue-100 bg-blue-50/30 p-3 sm:rounded-xl sm:p-4">
      {/* 标题 */}
      <h3 className="mb-3 text-sm font-semibold text-gray-800">
        📋 {productName} — 保障一览
      </h3>

      {/* 保障项列表 */}
      <div className="space-y-2">
        {duties.map((duty, index) => (
          <div
            key={index}
            className="flex items-start gap-2 text-sm"
          >
            {/* 必选/可选标签 */}
            <span
              className={`mt-0.5 inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium ${
                duty.is_optional
                  ? "bg-gray-100 text-gray-500"
                  : "bg-blue-100 text-blue-600"
              }`}
            >
              {duty.is_optional ? "可选" : "必选"}
            </span>

            {/* 名称 */}
            <span className="min-w-0 flex-1 text-gray-700">
              {duty.name}
            </span>

            {/* 额度 */}
            {duty.coverage && (
              <span className="max-w-[42%] shrink-0 break-words text-right font-medium text-green-600 sm:max-w-none">
                {duty.coverage}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* 底部统计 */}
      <p className="mt-3 text-xs text-gray-400">
        共 {duties.length} 项保障（{duties.filter(d => !d.is_optional).length} 必选 + {duties.filter(d => d.is_optional).length} 可选）
      </p>
    </div>
  );
}
