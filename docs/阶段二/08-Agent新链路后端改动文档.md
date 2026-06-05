# Agent 新链路后端改动文档

状态：方案设计中  
适用范围：Go Eino 后端、Agent Runtime、新 Agent Graph、SSE API、MySQL/Redis 会话记忆  
关联前端文档：`07-Agent新链路前端改动文档.md`

## 一、背景

当前后端已有稳定链路：

```text
/api/chat
  -> chatflow.Runner
  -> GraphFlow
  -> intent_model
  -> search_tool
  -> answer_model
  -> finish
```

现在需要新增一条 Agent 链路，而不是拆掉或替换当前链路。

目标形态：

```text
/api/chat
  -> 旧链路，继续保留

/api/agent/chat
  -> AgentRuntime
  -> SmartInsureAdvisorAgent
  -> AgentGraph
  -> SSE
```

旧链路作为稳定生产入口和回滚路径，新链路用于承载 Agent 化编排、工具调用、短期记忆节点化和后续 MCP 化能力。

## 二、目标

1. 新增 `/api/agent/chat`，不影响现有 `/api/chat`。
2. 新建 Agent Runtime，统一 Agent 注册、请求、事件输出。
3. 新建 `SmartInsureAdvisorAgent`，承载保险咨询新链路。
4. 新 Agent 链路使用独立 Graph，不直接改造现有 `GraphFlow`。
5. 新链路复用已有 LLM 配置、MySQL 会话、Redis 短期记忆、产品搜索和详情能力。
6. SSE 协议第一版兼容旧链路，便于前端低成本接入。

## 三、非目标

1. 不删除 `/api/chat`。
2. 不把所有模块一次性拆成多个自治 Agent。
3. 不在第一版引入远程 MCP 服务。
4. 不改变已有 MySQL/Redis 表结构，除非新链路确实需要增加 metadata 字段。
5. 不强制前端第一版展示 Agent 思考过程。

## 四、后端新增模块

建议新增目录：

```text
internal/agent/runtime/
  agent.go
  request.go
  event.go
  registry.go

internal/agent/smartinsureagent/
  agent.go
  graph.go
  state.go
  nodes.go
  tools.go
  memory.go

internal/api/
  agent_router.go
```

### 4.1 Agent 接口

```go
type Agent interface {
    ID() string
    Run(ctx context.Context, req AgentRequest) <-chan AgentEvent
}
```

### 4.2 AgentRequest

```go
type AgentRequest struct {
    RequestID     string
    AgentID       string
    AnonymousID   string
    ChatSessionID string
    UserID        string
    Message       string
    Action        string
    ProductURL    string
    ProductName   string
    Metadata      map[string]any
}
```

### 4.3 AgentEvent

```go
type AgentEvent struct {
    Name      string
    Data      any
    RequestID string
    AgentID   string
    TraceID   string
}
```

第一版可以把 `AgentEvent` 映射为现有 SSE：

```text
status
products
detail_items
delta
sources
disclaimer
done
error
```

## 五、新 Agent Graph 设计

新链路建议单独实现 `AgentGraph`：

```text
START
 -> session_validate
 -> memory_load
 -> agent_intent_prompt
 -> agent_intent_model
 -> agent_intent_parse
 -> agent_route
 -> product_search_tool
 -> knowledge_search_tool
 -> agent_answer_prompt
 -> agent_answer_model
 -> answer_stream_emit
 -> memory_save
 -> finish
 -> END
```

分支说明：

```text
product_detail action
  -> product_detail_node
  -> memory_save
  -> finish

needs_followup
  -> followup_prompt
  -> followup_model
  -> followup_emit
  -> memory_save
  -> finish

out_of_scope
  -> out_of_scope_emit
  -> memory_save
  -> finish
```

## 六、节点职责

| 节点 | 职责 |
|---|---|
| `session_validate` | 校验 `anonymous_id`、`chat_session_id` 归属 |
| `memory_load` | 从 Redis 读取最近 N 条消息，未命中则 MySQL 回源 |
| `agent_intent_model` | 使用 Eino ChatModelNode 判断意图 |
| `agent_route` | 根据意图分流到搜索、详情、追问或超范围 |
| `product_search_tool` | 调用当前产品搜索能力，返回产品卡片 |
| `knowledge_search_tool` | 调用知识检索或 fallback search，返回 sources |
| `agent_answer_model` | 使用 Eino ChatModelNode 生成回答 |
| `answer_stream_emit` | 把模型流式输出转换为 SSE delta |
| `memory_save` | 聚合 user/assistant 消息，写 MySQL 和 Redis |
| `finish` | 输出 sources、disclaimer、done |

## 七、Tool 设计

第一版 Tool 仍使用 in-process 实现，保持稳定：

| Tool | 第一版实现 | 后续方向 |
|---|---|---|
| `product_search_tool` | 复用当前产品搜索服务 | 可迁移为 MCP Tool |
| `knowledge_search_tool` | 复用 fallback/RAG 检索 | 可迁移为 MCP/RAG Tool |
| `product_detail_tool` | 复用详情抓取和解析服务 | 可独立成 ProductDetailAgent |

注意：搜索是工具，不建议第一版做成自治 Agent。它没有独立规划目标，属于确定性能力调用。

## 八、接口设计

新增接口：

```http
POST /api/agent/chat
Accept: text/event-stream
Content-Type: application/json
```

请求示例：

```json
{
  "anonymous_id": "anon_xxx",
  "chat_session_id": "chat_xxx",
  "message": "百万医疗险怎么选？",
  "stream": true,
  "metadata": {
    "source": "web"
  }
}
```

商品详情：

```json
{
  "anonymous_id": "anon_xxx",
  "chat_session_id": "chat_xxx",
  "action": "product_detail",
  "product_url": "https://example.com/product",
  "product_name": "某百万医疗险"
}
```

产品追问：

```json
{
  "anonymous_id": "anon_xxx",
  "chat_session_id": "chat_xxx",
  "action": "product_followup",
  "product_url": "https://example.com/product",
  "message": "外购药能报吗？"
}
```

## 九、SSE 输出要求

新链路第一版必须保持旧事件兼容：

```text
event: status
data: {"stage":"analyzing","message":"正在分析您的问题...","agent_id":"smartinsure-advisor","trace_id":"trace_xxx"}

event: products
data: {"items":[...],"agent_id":"smartinsure-advisor","trace_id":"trace_xxx"}

event: delta
data: {"text":"...","agent_id":"smartinsure-advisor","trace_id":"trace_xxx"}

event: done
data: {"requestId":"...","agent_id":"smartinsure-advisor","trace_id":"trace_xxx"}
```

兼容原则：

1. 事件名优先兼容旧前端。
2. 新增字段只能追加，不能破坏旧字段。
3. `done` 必须作为正常结束信号。
4. 异常时输出 `error`，并关闭 SSE。

## 十、会话与记忆

新链路必须接入已有 MySQL/Redis 设计：

```text
收到请求
  -> session_validate
  -> 写入 user message
  -> memory_load 读取最近 N 条
  -> AgentGraph 执行
  -> 聚合 assistant 输出
  -> memory_save 写入 assistant message
```

写入原则：

1. 用户消息在执行 Agent 前写入。
2. assistant 消息在 SSE 正常完成后写入。
3. Redis 是热缓存，MySQL 是最终可信存储。
4. Redis 故障时允许降级到 MySQL，不阻断主链路。

## 十一、配置项

建议新增：

```text
AGENT_CHAT_ENABLED=true
AGENT_DEFAULT_ID=smartinsure-advisor
AGENT_MEMORY_WINDOW=10
AGENT_TRACE_ENABLED=true
```

保留现有：

```text
ORCHESTRATOR=eino_graph
```

注意：`ORCHESTRATOR` 控制旧 `/api/chat` 的编排模式；`AGENT_CHAT_ENABLED` 控制新 `/api/agent/chat` 是否开放。

## 十二、观测与日志

每次 Agent 请求需要生成：

| 字段 | 说明 |
|---|---|
| `trace_id` | 单次 Agent 执行追踪 ID |
| `request_id` | 前端请求 ID |
| `agent_id` | 当前 Agent |
| `session_id` | 当前聊天会话 |
| `stage` | 当前节点阶段 |
| `latency_ms` | 总耗时 |
| `tool_latency_ms` | Tool 调用耗时 |
| `model_latency_ms` | 模型调用耗时 |

日志不要输出 API Key、Redis 密码、完整用户敏感信息。

## 十三、测试计划

后端需要覆盖：

1. `/api/agent/chat` 普通聊天 SSE 完整性。
2. `/api/agent/chat` 产品推荐返回 `products`。
3. 知识科普问题不返回产品卡。
4. 商品详情和商品追问可走新链路。
5. session 校验失败返回明确错误。
6. Redis 不可用时可 MySQL 回源。
7. Agent 新链路与旧 `/api/chat` 使用同一批 6 角色用例对比。
8. 产品卡片字段完整性评分。
9. 响应耗时、最快、最慢、平均值对比。

## 十四、验收标准

1. 不影响现有 `/api/chat`。
2. `/api/agent/chat` 能独立完成普通聊天、产品推荐、知识问答、详情、追问。
3. SSE 事件与旧链路兼容。
4. 能正确写入和读取 MySQL/Redis 会话记忆。
5. 同一批 6 角色用例无 error，SSE 完整率 100%。
6. 产品卡片字段完整性不低于当前链路。
7. 响应耗时不得显著劣化，平均耗时超过旧链路 30% 需定位原因。

## 十五、实施顺序

推荐分阶段落地：

1. 新增 Agent Runtime 和 `/api/agent/chat` 空壳。
2. 新增 `SmartInsureAdvisorAgent`，先返回固定 SSE，验证接口。
3. 接入 AgentGraph 的 intent 和 answer ChatModelNode。
4. 接入 product search 和 knowledge search Tool。
5. 接入 product detail / followup。
6. 接入 MySQL/Redis memory load/save。
7. 跑同用例回归、产品卡评分和耗时对比。
8. 前端通过配置切换到 `agent_chat` 验证。
