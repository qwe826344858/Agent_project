# 阶段一MVP文档索引

状态：已完成（文档层）

## 一、文档清单

1. [需求梳理与阶段拆解.md](/home/zhaoting/project/Agent/docs/阶段一MVP/需求梳理与阶段拆解.md)
2. [技术方案设计.md](/home/zhaoting/project/Agent/docs/阶段一MVP/技术方案设计.md)
3. [接口定义.md](/home/zhaoting/project/Agent/docs/阶段一MVP/接口定义.md)
4. [Prompt设计.md](/home/zhaoting/project/Agent/docs/阶段一MVP/Prompt设计.md)
5. [测试计划与报告.md](/home/zhaoting/project/Agent/docs/阶段一MVP/测试计划与报告.md)
6. [上线与复盘.md](/home/zhaoting/project/Agent/docs/阶段一MVP/上线与复盘.md)
7. [模块逐条映射表.md](/home/zhaoting/project/Agent/docs/阶段一MVP/模块逐条映射表.md)

### 产品推荐双通道方案（跨专题，已拆分归档）

8. [后端专题/05-产品推荐双通道方案-后端.md](后端专题/05-产品推荐双通道方案-后端.md) — 双通道架构、SSE协议、ProductSearchService
9. [前端专题/06-产品推荐双通道方案-前端.md](前端专题/06-产品推荐双通道方案-前端.md) — ProductCardList组件、渐进式加载
10. [LLM专题/05-产品推荐双通道方案-LLM.md](LLM专题/05-产品推荐双通道方案-LLM.md) — LLM职责调整、Prompt变更

## 二、推荐执行顺序

1. 先读 `需求梳理与阶段拆解`，确认范围与里程碑。
2. 再读 `技术方案设计`，确认架构与部署约束。
3. 再读 `接口定义` 与 `Prompt设计`，完成前后端联调基线。
4. 按 `测试计划与报告` 执行验收测试。
5. 按 `上线与复盘` 进行发布、观察与问题闭环。

## 三、当前结论

1. 阶段一文档体系已完整并可执行。
2. 部署方式已统一为单一 `docker-compose.yml` 与单一 `.env.example`。
3. 后端主框架为 FastAPI，编排层已预留后续迁移 LangGraph 的解耦策略。

## 四、下一步（实施阶段）

1. 初始化 `apps/frontend`（Next.js）与 `apps/backend`（FastAPI）工程骨架。
2. 按接口定义实现 `GET /api/healthz`、`GET /api/suggestions`、`POST /api/chat(SSE)`。
3. 按 Prompt 设计实现意图识别、搜索词生成、答案生成三段链路。
