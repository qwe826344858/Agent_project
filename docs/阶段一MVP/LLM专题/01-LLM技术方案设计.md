# LLM技术方案设计（阶段一MVP）

状态：已完成

## 一、目标与范围

1. 提供稳定、可解释、可溯源的生成能力。
2. 将 LLM 能力拆分为三个子任务：意图识别、搜索词生成、答案生成。
3. 控制幻觉与合规风险，保证输出边界。

## 二、框架与组件

1. 调用适配层：LiteLLM
2. 编排方式：轻量函数编排（预留 LangGraph 替换点）
3. Prompt 管理：模板化存储，按版本发布（如 `prompt_v1.0`）
4. 输出校验：JSON Schema（意图与搜索词阶段）

## 三、模型调用设计

1. `classify_intent(message)` -> JSON
2. `gen_queries(message, intent)` -> JSON
3. `gen_answer(message, search_context)` -> 结构化文本

建议参数：

1. 意图/搜索词：低温（0.1~0.3）
2. 答案生成：中低温（0.3~0.5）
3. 超时：8~12秒，失败重试1~2次

## 四、风险控制

1. 强制基于检索结果作答。
2. 信息不足时触发追问，不强行推荐。
3. 不确定信息明确标记“未找到明确信息”。
4. 固定免责声明统一输出。

## 五、可迁移性设计

1. 使用 `Orchestrator Adapter` 隔离具体编排实现。
2. 业务层仅依赖服务接口，不耦合 LangChain/LangGraph 细节。
3. 通过配置切换编排实现：`ORCHESTRATOR=lite|langgraph`。

