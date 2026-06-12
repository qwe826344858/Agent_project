"""产品详情全局缓存 — URL 级别，TTL 1 天

产品页面链接通过平台 API 获取，内容稳定，缓存 1 天可有效避免重复抓取。
首次查询走完整链路（抓取+提取+翻译），后续追问直接从缓存取结构化数据。
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 需要延迟导入以避免循环依赖，在类型注解中用字符串
# ProductDetail 类型在 app.schemas.chat 中定义


@dataclass
class CacheEntry:
    """缓存条目"""
    detail: object               # ProductDetail 实例
    created_at: datetime = field(default_factory=datetime.now)
    ttl: timedelta = field(default_factory=lambda: timedelta(days=1))

    @property
    def is_expired(self) -> bool:
        return datetime.now() - self.created_at > self.ttl


class ProductDetailCache:
    """全局 URL 级产品详情缓存

    线程安全，支持 TTL 过期自动清理。
    """

    def __init__(self, default_ttl: timedelta | None = None):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl or timedelta(days=1)

    def get(self, url: str):
        """获取缓存，过期则自动删除返回 None"""
        with self._lock:
            entry = self._store.get(url)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[url]
                logger.info("缓存过期: %s", url[:60])
                return None
            logger.info("缓存命中: %s", url[:60])
            return entry.detail

    def set(self, url: str, detail) -> None:
        """写入缓存"""
        with self._lock:
            self._store[url] = CacheEntry(
                detail=detail,
                created_at=datetime.now(),
                ttl=self._default_ttl,
            )
            logger.info("缓存写入: %s (当前缓存数: %d)", url[:60], len(self._store))

    def clear_expired(self) -> int:
        """清理所有过期条目，返回清理数量"""
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired]
            for k in expired_keys:
                del self._store[k]
            if expired_keys:
                logger.info("清理过期缓存: %d 条", len(expired_keys))
            return len(expired_keys)

    def size(self) -> int:
        """返回当前缓存条目数"""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """清空全部缓存"""
        with self._lock:
            self._store.clear()


# 全局单例
product_detail_cache = ProductDetailCache()
