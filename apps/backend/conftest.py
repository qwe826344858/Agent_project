"""pytest 全局配置"""
import asyncio
import pytest


def pytest_configure(config):
    """注册 asyncio marker"""
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture(autouse=True)
def _reset_sse_starlette_state():
    """每个测试前重置 sse-starlette 的全局 AppStatus 事件，
    避免 'Event is bound to a different event loop' 错误"""
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = asyncio.Event()
    except (ImportError, AttributeError):
        pass
    yield
