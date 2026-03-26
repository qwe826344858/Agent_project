"""FastAPI 应用入口"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.core.logging import RequestIdMiddleware
from app.api.healthz import router as healthz_router
from app.api.suggestions import router as suggestions_router
from app.api.chat import router as chat_router
from app.api.providers import router as providers_router

# 日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="SmartInsure Agent API",
    description="AI智能保险顾问后端服务",
    version="0.1.0",
)

# 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)

# 异常处理
app.add_exception_handler(AppError, app_error_handler)

# 路由注册
app.include_router(healthz_router, prefix="/api")
app.include_router(suggestions_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(providers_router, prefix="/api")
