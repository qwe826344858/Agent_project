# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SmartInsure Agent** — AI智能保险顾问，Web 对话式保险问答应用。采用双通道架构：产品卡片由平台直连 API 获取真实数据（通道A），文字建议由 LLM 流式生成（通道B）。

## Architecture

```
用户输入 → 意图识别(LLM) → 并行执行:
  通道A: platform_apis/ → 小雨伞/平安/慧择 API → 预算筛选 → SSE products 事件
  通道B: fallback 知识库 → LLM 流式回答 → SSE delta 事件
→ sources → disclaimer → done
```

**后端 (FastAPI)** — `apps/backend/`
- `app/api/chat.py` → `orchestrator_adapter.py` → `chat_orchestrator.py`（编排器）
- `app/services/platform_apis/`：平台直连 API（**产品数据来源**，不依赖搜索引擎）
  - `base.py`（抽象基类）→ `xiaoyusan.py`、`pingan.py`、`huize.py`
  - 新增平台：继承 `PlatformAPI`，实现 `search()` 方法，在 `__init__.py` 注册
- `app/services/llm_client.py`：LLM 调用（LiteLLM 封装），自动过滤 `<think>` 思维链
- `app/services/prompts.py`：Prompt 模板（v1.2），LLM 不生成产品链接/价格
- `app/config/llm_providers.yaml`：多模型配置（当前 MiniMax-M2.5-highspeed + OpenAI 协议）
- `app/core/llm_providers.py`：从 YAML 加载 Provider 配置的注册中心

**前端 (Next.js)** — `apps/frontend/`
- SSE 直连后端 8000 端口（不走 Next.js rewrites 代理，避免缓冲）
- 前端端口 **3001**（3000 留给 MCP 服务）
- `ProductCardList.tsx`：产品卡片组件（含真实投保链接和价格）

## Build & Deploy Commands

### 一键部署

```bash
./deploy.sh dev      # 开发模式（代码挂载 + 热重载）
./deploy.sh start    # 生产模式（构建镜像）
./deploy.sh restart  # 重启（不重建镜像）
./deploy.sh stop     # 停止
./deploy.sh check    # 健康检查
./deploy.sh logs backend   # 后端日志
./deploy.sh logs frontend  # 前端日志
```

### 后端测试

```bash
# 远端 Docker 内运行
docker exec compose-backend-1 python3 -m pytest tests/ -v

# 单个测试
docker exec compose-backend-1 python3 -m pytest tests/test_chat.py -v

# 性能基线
docker exec compose-backend-1 python3 tests/perf_baseline.py --base-url http://localhost:8000
```

### 前端测试

```bash
cd apps/frontend && npm test
```

### 远程部署调试规则

- **禁止**：非必要情况下重新构建镜像（`--build`）
- **必须**：通过 volume 挂载源码，修改后 `restart` 即可生效
- **仅允许 rebuild 的场景**：修改 `requirements.txt` 或 `Dockerfile`
- 后端开发模式启用 `uvicorn --reload`，Python 代码改动自动热重载
- YAML 配置文件变更需 `--force-recreate` 才能生效（uvicorn 不监控 .yaml）
- 远程机器：`ssh yunxigu@192.168.2.66`（密码 yunxigu2025），项目目录 `/Users/yunxigu/cc_project/Agent_project`
- `.env` 文件已从 auto_sync 中排除，远端手动修改不会被覆盖

## Key SSE Events

| 事件 | 说明 |
|---|---|
| `status` | 阶段状态（analyzing/searching/answering） |
| `products` | 产品卡片（含价格和投保链接，由平台 API 直接返回） |
| `delta` | LLM 流式文本 |
| `sources` | 参考来源 |
| `disclaimer` | 免责声明 |
| `done` | 完成 |
| `error` | 错误 |

## LLM 配置

通过 `app/config/llm_providers.yaml` 配置，切换模型只需改 YAML：
- `prefix`：LiteLLM 协议前缀（`openai` / `anthropic` / `minimax` 等）
- `default_model`：模型名
- `default_base`：API 端点
- 环境变量 `MINIMAX_API_BASE` 会覆盖 YAML 中的 `default_base`

## 平台直连 API

产品数据通过直接调用保险平台搜索 API 获取，不依赖搜索引擎：

| 平台 | API | 认证 |
|---|---|---|
| 小雨伞 | `POST /index/searchData` (form-data) | 需要浏览器 Cookie（`XYS_COOKIE` 环境变量） |
| 平安 | `GET /pa18shopnst/do/era/shopProduct/search?keyword=` | 无需认证 |
| 慧择 | `POST search.huize.com/api/v4/pc/search/product/list` (JSON) | 无需认证（Referer 中文需 URL 编码） |

新增平台：在 `app/services/platform_apis/` 下新建文件，继承 `PlatformAPI`，实现 `search()` 方法，在 `__init__.py` 的 `PLATFORMS` 列表注册。

## 回归验证

每次阶段性功能迭代完成后，必须按 `docs/回归验证功能点清单.md` 执行回归：
1. 后端全量测试：`cd apps/backend && python3 -m pytest tests/ -v`（当前 121 个用例）
2. 前端全量测试：`cd apps/frontend && npm test`（当前 18 个用例）
3. 14 场景端到端回归：`python3 persona_test_v2.py`
4. 结果记录到清单文档的"回归记录"表

## Coding Conventions

- **Python**：PEP 8，4 空格缩进，类型注解，中文注释
- **TypeScript**：2 空格缩进，变量/函数 `camelCase`，组件 `PascalCase`
- **测试**：后端 `test_*.py`，前端 `*.test.ts(x)`
- **提交信息**：`type(scope): summary`

## Key Design Constraints

- 产品投保链接和价格由**代码逻辑**从平台 API 精确获取，**不经过 LLM**
- LLM 只负责文字建议（选购分析、风险提示），Prompt 中明确禁止输出链接和价格
- 编排层与领域逻辑严格分离，Prompt/搜索/模型调用走独立服务模块
- 用户预算筛选：从输入中提取年预算，月缴×12 估算年缴，按匹配度排序（容差 50%）
- `<think>` 思维链在 `llm_client.py` 中自动过滤，前端不会看到
- 环境变量通过 `.env` 注入，密钥禁止提交到代码库

## Skills

### agent-teams-module-delivery

多 Agent 协作开发技能（`skills/agent-teams-module-delivery/SKILL.md`）。流程：理解文档 → Leader 拆分任务 → Agent 并行开发 → 自测 → 验证 → 归档。每个模块必须"代码 + 注释 + 测试 + 结果记录"四项齐全。

### add-insurance-platform

新增保险平台 API 接入技能（`skills/add-insurance-platform/SKILL.md`）。用户提供 curl 示例和响应 JSON，自动生成平台适配器代码、注册到 PLATFORMS、编写测试并验证通过。

### regression-verify

回归验证技能（`skills/regression-verify/SKILL.md`）。阶段性迭代完成后调用，自动执行：全量单元测试 → 端到端 14 角色回归 → 逐项验证 → 更新回归记录。确保历史功能点不被破坏。
