# Repository Guidelines

## Project Structure & Module Organization
当前仓库以“文档 + 部署模板”为主，结构如下：

- `docs/`：产品与规划文档（如 `docs/阶段一MVP/`、`docs/战略规划/`）。
- `deploy/`：Docker 部署资源。
  - `deploy/compose/docker-compose.yml`：唯一部署入口。
  - `deploy/docker/frontend/`、`deploy/docker/backend/`：前后端镜像构建文件。
  - `deploy/env/.env.example`：统一环境变量模板。
- `script/`：辅助脚本（如 `script/auto_sync.sh`）。

后续若新增应用代码，建议放在 `apps/frontend`（Next.js）与 `apps/backend`（FastAPI），与现有部署模板保持一致。

## Build, Test, and Development Commands
- 启动全栈（本地）：
  - `docker compose -f deploy/compose/docker-compose.yml --env-file deploy/env/.env.example up -d --build`
- 停止服务：
  - `docker compose -f deploy/compose/docker-compose.yml down`
- 重建单个服务（示例）：
  - `docker compose -f deploy/compose/docker-compose.yml build frontend`

说明：如果 `apps/frontend` 或 `apps/backend` 目录尚未创建，构建失败属于预期行为。

## Coding Style & Naming Conventions
- 文档统一使用 UTF-8 Markdown，标题简短、可执行。
- 文件名应语义明确；规划类文档可继续使用中文命名。
- 未来代码规范：
  - Next.js/TypeScript：2 空格缩进，变量/函数 `camelCase`，组件 `PascalCase`。
  - FastAPI/Python：遵循 PEP 8，4 空格缩进，要求类型注解。

## Testing Guidelines
- 新增代码需配套测试：
  - 前端：`*.test.ts(x)`
  - 后端：`test_*.py`
- 优先覆盖关键链路：聊天接口、搜索编排、SSE 流式输出、错误处理。
- 发布前必须在 CI 中通过测试；测试失败禁止发布。

## Commit & Pull Request Guidelines
当前工作区尚无可参考的 Git 历史，统一采用以下约定：

- 提交信息格式：`type(scope): summary`  
  示例：`feat(deploy): simplify to single docker compose config`
- PR 必须包含：
  - 变更摘要
  - 影响路径
  - 验证步骤/命令
  - 涉及界面或文档结构变化时附截图

## Security & Configuration Tips
- 禁止提交真实 API Key 或其他密钥。
- `.env.example` 仅保留模板字段，生产密钥通过部署环境注入。
- 所有搜索/LLM 外部调用必须设置超时与重试策略。
