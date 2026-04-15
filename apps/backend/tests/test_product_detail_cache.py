"""产品详情缓存模块单元测试"""

import time
from datetime import timedelta

import pytest

from app.services.product_detail_cache import ProductDetailCache


@pytest.fixture
def cache() -> ProductDetailCache:
    """每个测试用例使用独立的缓存实例"""
    return ProductDetailCache()


class TestProductDetailCache:
    """ProductDetailCache 单元测试"""

    def test_set_and_get(self, cache: ProductDetailCache):
        """set 后 get 返回同一对象"""
        detail = {"name": "重疾险A", "price": 1200}
        cache.set("https://example.com/product/1", detail)
        result = cache.get("https://example.com/product/1")
        assert result is detail

    def test_get_not_found(self, cache: ProductDetailCache):
        """未 set 的 key 返回 None"""
        result = cache.get("https://example.com/not-exist")
        assert result is None

    def test_expired_entry(self):
        """用很短的 TTL，sleep 后 get 返回 None"""
        cache = ProductDetailCache(default_ttl=timedelta(milliseconds=100))
        detail = {"name": "医疗险B"}
        cache.set("https://example.com/product/2", detail)

        # 确认写入成功
        assert cache.get("https://example.com/product/2") is detail

        # 等待过期
        time.sleep(0.2)

        # 过期后应返回 None
        assert cache.get("https://example.com/product/2") is None

    def test_clear_expired(self):
        """创建已过期的条目，clear_expired 清理它"""
        cache = ProductDetailCache(default_ttl=timedelta(milliseconds=100))
        cache.set("https://example.com/a", {"name": "A"})
        cache.set("https://example.com/b", {"name": "B"})

        # 等待过期
        time.sleep(0.2)

        # 添加一条未过期的（使用默认 1 天 TTL 的新缓存实例的条目模拟）
        # 直接操作内部存储以添加一条新鲜条目
        from app.services.product_detail_cache import CacheEntry
        from datetime import datetime
        with cache._lock:
            cache._store["https://example.com/c"] = CacheEntry(
                detail={"name": "C"},
                created_at=datetime.now(),
                ttl=timedelta(days=1),
            )

        cleaned = cache.clear_expired()
        assert cleaned == 2
        assert cache.size() == 1
        assert cache.get("https://example.com/c") is not None

    def test_size(self, cache: ProductDetailCache):
        """set 3 条，size() == 3"""
        cache.set("https://example.com/1", {"id": 1})
        cache.set("https://example.com/2", {"id": 2})
        cache.set("https://example.com/3", {"id": 3})
        assert cache.size() == 3

    def test_clear_all(self, cache: ProductDetailCache):
        """clear() 后 size() == 0"""
        cache.set("https://example.com/1", {"id": 1})
        cache.set("https://example.com/2", {"id": 2})
        assert cache.size() == 2
        cache.clear()
        assert cache.size() == 0

    def test_overwrite(self, cache: ProductDetailCache):
        """同一 URL set 两次，get 返回后一次的值"""
        url = "https://example.com/product/dup"
        first = {"version": 1}
        second = {"version": 2}
        cache.set(url, first)
        cache.set(url, second)
        result = cache.get(url)
        assert result is second
        assert cache.size() == 1
