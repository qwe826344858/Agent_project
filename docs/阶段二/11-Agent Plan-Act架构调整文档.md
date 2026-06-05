# Agent Plan-Act 架构调整文档

状态：方案设计中  
适用范围：前端 `/chat/agent`、Go Eino 后端、AgentRuntime、SmartInsureAdvisorAgent、Plan-Act AgentGraph、Tool 执行、SSE 协议  
关联文档：`07-Agent新链路前端改动文档.md`、`08-Agent新链路后端改动文档.md`

## 一、背景

当前项目已经拆出两条入口：

```text
/ 
  -> legacy_chat
  -> /api/chat
  -> workflow

/chat/agent
  -> agent_chat
  -> /api/agent/chat
  -> AgentRuntime
  -> SmartInsureAdvisorAgent
  -> AgentGraph
```

但当前 `SmartInsureAdvisorAgent -> AgentGraph` 仍然偏固定流程：

```text
session_validate
 -> memory_load
 -> intent_model
 -> agent_route
 -> product_search_tool
 -> knowledge_search_tool
 -> answer_model
 -> finish
```

这解决了“新 Agent 入口”和“独立 AgentGraph”问题，但还不是典型 Agent 交互。原因是工具调用顺序主要由代码固定，模型没有根据目标、上下文和工具观察结果动态决定下一步。

本调整文档目标是将 `/chat/agent` 后端链路升级为受控 Plan-Act Agent，而不是继续扩大固定 workflow。

## 二、核心判断

### 2.1 当前更像 workflow 的原因

| 维度 | 当前实现 | Agent 期望 |
|---|---|---|
| 执行顺序 | 代码固定节点顺序 | 模型基于目标决定下一步 |
| 工具选择 | intent 后固定调用搜索/详情 | 模型选择 action |
| 观察反馈 | 工具结果直接进入回答 | observation 进入 scratchpad 后再次决策 |
| 循环能力 | 基本单轮执行 | 多轮 `plan -> act -> observe -> replan` |
| 结束条件 | 代码固定 finish | 模型输出 `final_answer` 或 `ask_followup` |
| 内部状态 | 只有 history/results/sources | 需要 plan、steps、observations、iteration |

### 2.2 目标 Agent 形态

目标不是完全自由 Agent，而是受控 Agent：

```text
模型可以决定下一步做什么
但只能在白名单 action 中选择
每轮 action 都由后端校验
工具调用有超时和次数限制
最终输出必须符合保险合规格式
```

推荐目标：

```text
AgentRuntime + Plan-Act SmartInsureAdvisorAgent
```

## 三、目标

1. `/` 继续走 legacy workflow，不影响稳定链路。
2. `/chat/agent` 走 Plan-Act AgentGraph。
3. AgentGraph 支持模型动态选择工具。
4. 工具结果以 observation 写回 AgentState，再进入下一轮决策。
5. 支持最多 N 轮工具调用，避免无限循环。
6. 继续兼容现有 SSE 事件：`status/products/detail_items/delta/sources/disclaimer/done/error`。
7. 不向前端暴露完整 thought，仅展示安全的状态信息。
8. 保持保险合规：不输出绝对承诺、不替代合同条款、不泄露密钥或敏感信息。

## 四、非目标

1. 不替换 `/api/chat`。
2. 不让前端实现 Agent 规划逻辑。
3. 不开放任意工具调用。
4. 不把完整模型 thought 展示给用户。
5. 不在第一版引入远程 MCP Tool。
6. 不一次性实现多 Agent 协作；当前仍是单个 `SmartInsureAdvisorAgent`。

## 五、入口分流

前端入口保持明确分流：

| 前端路由 | 前端模式 | 后端接口 | 后端链路 |
|---|---|---|---|
| `/` | `legacy_chat` | `/api/chat` | workflow |
| `/chat/agent` | `agent_chat` | `/api/agent/chat` | Plan-Act Agent |

前端代码约束：

```text
apps/frontend/src/app/page.tsx
  -> <ChatPageShell backendMode="legacy_chat" />

apps/frontend/src/app/chat/agent/page.tsx
  -> <ChatPageShell backendMode="agent_chat" />
```

后端代码约束：

```text
/api/chat
  -> s.flow.Run(...)

/api/agent/chat
  -> s.agentRuntime.Run(...)
  -> SmartInsureAdvisorAgent.Run(...)
  -> AgentGraph.Run(...)
```

## 六、目标 Plan-Act 流程

### 6.1 主流程

```text
START
 -> session_validate
 -> memory_load
 -> plan_init
 -> reason_model
 -> action_parse
 -> action_validate
 -> action_route
 -> tool_executor
 -> observation_append
 -> should_continue
 -> reason_model
 -> ...
 -> final_answer_stream
 -> memory_save
 -> finish
 -> END
```

### 6.2 详情直达流程

产品详情按钮可以直接走受控 action，不需要先让模型猜：

```text
START
 -> session_validate
 -> memory_load
 -> product_detail_tool
 -> observation_append
 -> final_answer_stream
 -> memory_save
 -> finish
 -> END
```

### 6.3 追问流程

```text
用户问题不完整
 -> reason_model
 -> action=ask_followup
 -> followup_emit
 -> memory_save
 -> done
```

### 6.4 超范围流程

```text
用户问题超出保险咨询范围
 -> reason_model
 -> action=final_answer
 -> 输出边界说明
 -> done
```

## 七、Action 设计

第一版只允许 5 个 action：

| Action | 说明 | 是否调用工具 | 前端事件 |
|---|---|---|---|
| `product_search` | 搜索保险产品卡片 | 是 | `status`、`products` |
| `knowledge_search` | 搜索保险知识、条款解释、来源 | 是 | `status`、`sources` |
| `product_detail` | 解析指定产品详情 | 是 | `status`、`detail_items`、`delta` |
| `ask_followup` | 追问用户补充信息 | 否 | `delta`、`done` |
| `final_answer` | 输出最终回答 | 否 | `delta`、`sources`、`disclaimer`、`done` |

禁止 action：

```text
open_url
http_request
shell
database_query
send_message
payment
quote_policy
```

## 八、Reasoner 输出协议

模型每轮只能输出 JSON，不允许输出自由文本：

```json
{
  "thought": "用户想选百万医疗险，需要先获取候选产品并关注续保、免赔额、外购药责任。",
  "action": "product_search",
  "action_input": {
    "query": "百万医疗险 保证续保 外购药 免赔额"
  }
}
```

最终回答：

```json
{
  "thought": "已有产品和知识来源，可以输出建议。",
  "action": "final_answer",
  "action_input": {
    "answer_brief": "按续保稳定性、免赔额、外购药和健康告知给出建议。"
  }
}
```

追问：

```json
{
  "thought": "缺少年龄、预算和健康情况，直接推荐风险较高。",
  "action": "ask_followup",
  "action_input": {
    "question": "为了更准确推荐，请补充被保人年龄、年预算和是否有既往症或体检异常。"
  }
}
```

说明：

1. `thought` 只进入后端 scratchpad，不直接发给前端。
2. `action` 必须在白名单内。
3. `action_input` 必须按 action schema 校验。
4. JSON 解析失败最多重试 1 次。

## 九、AgentState 设计

建议新增：

```go
type AgentState struct {
    Request      agentruntime.AgentRequest
    History      []ChatMessage
    Plan         string
    Steps        []AgentStep
    Products     []ProductCard
    Sources      []SourceItem
    DetailItems  []DetailItem
    FinalAnswer  string
    Iteration    int
}

type AgentStep struct {
    Thought     string
    Action      AgentAction
    ActionInput map[string]any
    Observation AgentObservation
    StartedAt   time.Time
    FinishedAt  time.Time
    Err         string
}

type AgentObservation struct {
    Summary string
    Data    map[string]any
}
```

状态使用原则：

1. `History` 来自 memory_load。
2. `Steps` 是本次 Agent 执行的 scratchpad。
3. Tool 原始结果可裁剪后进入 observation，避免 prompt 过长。
4. `Products/Sources/DetailItems` 是可展示结果，用于 SSE。

## 十、后端模块调整

建议落点：

```text
smartinsure-eino-backend/
  internal/agent/smartinsureagent/
    agent.go        # AgentRuntime 适配，trace 字段追加
    graph.go        # Plan-Act 主循环
    state.go        # AgentState / AgentStep / Observation
    planner.go      # reason_model prompt、模型调用、JSON 修复
    actions.go      # action schema、parse、validate、route、stop
    tools.go        # product_search / knowledge_search / product_detail
    memory.go       # memory_load / memory_save 适配层
    prompts.go      # Agent system prompt、planner prompt、final answer prompt
```

### 10.1 `agent.go`

职责：

1. 实现 `runtime.Agent`。
2. 调用 `AgentGraph.Run`。
3. 为 SSE data 追加 `agent_id`、`trace_id`、`requestId/request_id`。
4. 不做业务决策。

### 10.2 `graph.go`

职责：

1. 控制 Plan-Act 主循环。
2. 维护 iteration。
3. 根据 action 执行对应节点。
4. 负责最终收口。

核心伪代码：

```go
for state.Iteration < maxIterations {
    decision := reasoner.Next(ctx, state)
    action, err := validate(decision)
    if err != nil {
        appendInvalidActionObservation(state, err)
        continue
    }

    switch action.Name {
    case ActionProductSearch:
        obs := tools.ProductSearch(ctx, action.Input)
        appendObservation(state, obs)
        emitProducts(obs.Products)
    case ActionKnowledgeSearch:
        obs := tools.KnowledgeSearch(ctx, action.Input)
        appendObservation(state, obs)
    case ActionProductDetail:
        obs := tools.ProductDetail(ctx, action.Input)
        appendObservation(state, obs)
        emitDetailItems(obs.DetailItems)
    case ActionAskFollowup:
        emitDelta(action.Input.Question)
        done()
        return
    case ActionFinalAnswer:
        streamFinalAnswer(ctx, state)
        done()
        return
    }
}

fallbackFinalAnswer(ctx, state)
done()
```

### 10.3 `planner.go`

职责：

1. 构造 Plan-Act prompt。
2. 调用 LLM。
3. 解析 action JSON。
4. 处理 JSON 修复和 fallback。

输入包括：

```text
user message
history summary
available tools
current products
current sources
scratchpad observations
compliance rules
```

### 10.4 `tools.go`

第一版工具：

```go
type AgentTools interface {
    ProductSearch(ctx context.Context, input ProductSearchInput) (ProductSearchObservation, error)
    KnowledgeSearch(ctx context.Context, input KnowledgeSearchInput) (KnowledgeSearchObservation, error)
    ProductDetail(ctx context.Context, input ProductDetailInput) (ProductDetailObservation, error)
}
```

工具实现仍使用 in-process：

| Agent Tool | 第一版实现 |
|---|---|
| `product_search` | `service/productsearch` |
| `knowledge_search` | fallback search / RAG |
| `product_detail` | `skill/productdetail` |

## 十一、Prompt 设计

### 11.1 Planner System Prompt 要点

```text
你是 SmartInsureAdvisorAgent，一个保险咨询 Agent。
你需要在受控工具集合中选择下一步 action。
你只能输出 JSON。
你不能承诺一定赔付、一定投保成功、一定最优。
你不能输出保费精算结论，除非来自工具结果。
如果用户信息不足，优先 ask_followup。
如果已有足够 observation，输出 final_answer。
```

### 11.2 Tool 选择规则

```text
用户要推荐产品 -> product_search
用户问保险知识/条款概念 -> knowledge_search
用户点了具体产品或追问某产品 -> product_detail
缺少年龄、预算、健康情况且会影响建议 -> ask_followup
已有足够产品/知识/详情观察 -> final_answer
```

### 11.3 Final Answer Prompt 要点

最终回答必须包含：

```text
1. 结论或建议
2. 依据
3. 风险/限制
4. 下一步建议
5. 免责声明
```

不得包含：

```text
绝对化承诺
伪造条款
伪造来源
诱导投保
未经工具支持的价格/保障细节
```

## 十二、SSE 协议调整

继续兼容现有事件：

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

新增可选状态，不要求前端必须展示：

```text
event: status
data: {
  "stage": "reasoning",
  "message": "正在规划下一步..."
}

event: status
data: {
  "stage": "tool_running",
  "tool": "product_search",
  "message": "正在搜索保险产品..."
}

event: status
data: {
  "stage": "observing",
  "tool": "product_search",
  "message": "正在整理工具结果..."
}
```

前端处理原则：

1. 已知 status stage 正常展示。
2. 未知 stage 可展示通用“正在处理...”。
3. 不展示 `thought`。
4. `trace_id` 可仅用于调试面板或日志。

## 十三、安全与控制

必须设置：

```text
AGENT_MAX_ITERATIONS=4
AGENT_TOOL_TIMEOUT=15
AGENT_ACTION_REPAIR_ENABLED=true
AGENT_TRACE_ENABLED=true
```

硬性规则：

1. action 白名单校验。
2. action_input schema 校验。
3. 单工具超时。
4. 总请求超时。
5. 最大 iteration。
6. 连续无效 action 超过 2 次直接 fallback。
7. final answer 必须过合规过滤。
8. thought 不写入用户可见 SSE。
9. 日志不得输出 API Key、Redis 密码、完整敏感健康信息。

## 十四、配置项

建议新增：

```text
AGENT_MODE=plan_act
AGENT_MAX_ITERATIONS=4
AGENT_TOOL_TIMEOUT=15
AGENT_ACTION_REPAIR_ENABLED=true
AGENT_SCRATCHPAD_MAX_CHARS=6000
AGENT_OBSERVATION_MAX_CHARS=2000
```

保留：

```text
AGENT_CHAT_ENABLED=true
AGENT_DEFAULT_ID=smartinsure-advisor
AGENT_MEMORY_WINDOW=10
AGENT_TRACE_ENABLED=true
```

说明：

1. `AGENT_MODE=deterministic_graph` 可作为回滚模式。
2. `AGENT_MODE=plan_act` 是目标模式。
3. `/api/chat` 不受 `AGENT_MODE` 影响。

## 十五、测试计划

### 15.1 单元测试

| 测试 | 目标 |
|---|---|
| action JSON parse | 解析合法 action |
| action whitelist | 拒绝未知 action |
| action_input schema | 校验不同 action 的输入 |
| max iterations | 超限后 fallback final answer |
| invalid action repair | JSON 错误可修复或 fallback |
| product_search | 返回 products 并写 observation |
| knowledge_search | 返回 sources 并写 observation |
| product_detail | 返回 detail_items 并写 observation |
| ask_followup | 直接 delta + done |
| final_answer | 流式输出 delta + disclaimer + done |

### 15.2 API 测试

1. `/api/chat` 仍走 workflow，不包含 `agent_id`。
2. `/api/agent/chat` 走 Plan-Act Agent，包含 `agent_id`、`trace_id`。
3. `/api/agent/chat` 不调用旧 `chatflow.Runner.Run`。
4. agent 产品推荐返回 `products`。
5. agent 知识问答返回 `sources`。
6. agent 产品详情返回 `detail_items`。
7. trace disabled 时不输出 `trace_id`。
8. session 不存在时返回明确错误。

### 15.3 前端测试

1. `/` 使用 `legacy_chat`。
2. `/chat/agent` 使用 `agent_chat`。
3. `agent_chat` 请求地址为 `/api/agent/chat`。
4. status 新 stage 不导致渲染失败。
5. products/detail_items/delta/sources/disclaimer/done 兼容。

## 十六、验收标准

1. `/api/chat` 行为不变。
2. `/chat/agent` 明确走 `/api/agent/chat`。
3. `/api/agent/chat` 内部为 Plan-Act 循环，不是固定 workflow。
4. 模型可以在白名单 action 中动态选择下一步。
5. 工具 observation 会进入下一轮 reasoner。
6. 最大 iteration、工具超时、action 校验全部生效。
7. SSE 兼容现有前端。
8. thought 不出现在前端可见内容。
9. 全量后端测试通过。
10. 前端关键 API 测试通过。

## 十七、实施顺序

建议分 4 阶段：

### 阶段 1：Plan-Act 框架

1. 新增 `state.go`、`actions.go`。
2. 新增 action schema 和 parser。
3. 将当前 deterministic AgentGraph 改为可循环 state machine。
4. 使用 fake reasoner 完成单元测试。

### 阶段 2：Reasoner 接入

1. 新增 `planner.go`。
2. 接入 LLM 输出 action JSON。
3. 增加 JSON repair/fallback。
4. 加 max iteration 和 invalid action 限制。

### 阶段 3：Tools 接入

1. 新增 `tools.go`。
2. 接入 product_search。
3. 接入 knowledge_search。
4. 接入 product_detail。
5. 将 observation 写回 scratchpad。

### 阶段 4：联调与验收

1. 跑 `/api/chat` 和 `/api/agent/chat` 对照测试。
2. 跑 `/` 和 `/chat/agent` 前端入口测试。
3. 跑产品卡片、详情解析、知识问答、追问场景。
4. 记录耗时、失败率、超时和 fallback 情况。

## 十八、回滚策略

保留两层回滚：

```text
前端回滚：
  /chat/agent 不对用户开放，继续使用 /

后端回滚：
  AGENT_MODE=deterministic_graph
  或 AGENT_CHAT_ENABLED=false
```

`/api/chat` 作为稳定链路，不参与 Plan-Act 改造。
