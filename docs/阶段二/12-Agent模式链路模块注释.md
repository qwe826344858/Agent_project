# Agent 模式链路模块注释

状态：已落地  
适用范围：前端 `/chat/agent`、`/api/agent/chat`、`AgentRuntime`、`SmartInsureAdvisorAgent`、`Plan-Act AgentGraph`  
后端项目：`/home/zhaoting/Agent/smartinsure-eino-backend`

## 一、整体链路

Agent 模式只服务前端 `/chat/agent` 入口，不替换首页 `/` 的旧 workflow。

```text
前端 /chat/agent
  -> ChatPageShell backendMode=agent_chat
  -> sendChatMessage(...)
  -> POST /api/agent/chat
  -> api.agentChat
  -> AgentRuntime.Run
  -> SmartInsureAdvisorAgent.Run
  -> AgentGraph.Run
  -> reasoner.Next
  -> validateDecision
  -> executeAction
  -> tool observation
  -> replan / final_answer
  -> SSE 返回前端
```

旧链路仍然独立：

```text
前端 /
  -> ChatPageShell backendMode=legacy_chat
  -> POST /api/chat
  -> s.flow.Run(...)
  -> workflow
```

## 二、前端入口模块

### 2.1 `/chat/agent` 路由

文件：`apps/frontend/src/app/chat/agent/page.tsx`

职责：

- 将页面入口声明为 Agent 模式。
- 通过 `<ChatPageShell backendMode="agent_chat" />` 告诉聊天组件使用 `/api/agent/chat`。
- 不在前端实现 Agent 规划逻辑，前端只负责展示 SSE 事件。

### 2.2 `/` 旧路由

文件：`apps/frontend/src/app/page.tsx`

职责：

- 将首页保留为旧 workflow 模式。
- 通过 `<ChatPageShell backendMode="legacy_chat" />` 继续请求 `/api/chat`。
- 用于回归和稳定访问，不受 AgentGraph 改造影响。

### 2.3 聊天壳组件

文件：`apps/frontend/src/components/ChatPageShell.tsx`

职责：

- 管理消息列表、产品卡片、选择中的产品、匿名身份和会话恢复。
- 发起 `sendChatMessage`，消费后端 SSE。
- 根据事件类型更新界面：
  - `status`：展示思考状态，如 `reasoning/tool_running/observing/answering`。
  - `products`：更新产品卡片列表。
  - `detail_items`：展示产品详情解析结果。
  - `delta`：流式追加助手回答。
  - `sources`：展示来源。
  - `disclaimer`：展示免责声明。
  - `done`：结束流式状态。

### 2.4 API 客户端

文件：`apps/frontend/src/lib/api.ts`

职责：

- 根据 `backendMode` 选择接口：
  - `legacy_chat` -> `/api/chat`
  - `agent_chat` -> `/api/agent/chat`
- 对 Agent 模式构造请求体：
  - `anonymous_id`
  - `chat_session_id`
  - `stream: true`
  - `metadata.source=web`
  - `action/product_url/product_name`
- 使用 SSE parser 消费流式响应。
- 对内网访问做 URL 归一化：当前页面来自内网 IP 时，避免浏览器请求 Docker 内部 hostname。

## 三、后端 API 模块

### 3.1 Agent HTTP 入口

文件：`internal/api/agent_router.go`

职责：

- 处理 `POST /api/agent/chat`。
- 校验方法、JSON body、空消息、Agent 开关。
- 解析请求字段：
  - `message`
  - `requestId`
  - `anonymous_id`
  - `chat_session_id`
  - `action`
  - `product_url/product_name`
- 根据 `anonymous_id/chat_session_id` 加载历史消息。
- 调用 `s.agentRuntime.Run(...)`，进入 AgentRuntime。
- 将 AgentEvent 转成 SSE 写回前端。
- 在有会话时，把助手回答保存到 MySQL/Redis 会话存储。

它和 `/api/chat` 的关键区别：

```text
/api/chat        -> s.flow.Run(...)
/api/agent/chat  -> s.agentRuntime.Run(...)
```

### 3.2 Server 初始化

文件：`internal/api/router.go`

职责：

- 创建 legacy flow。
- 创建 AgentRuntime registry。
- 注册 `SmartInsureAdvisorAgent`。
- 将 `/api/agent/chat` 路由绑定到 `server.agentChat`。
- 保证旧 flow 和 AgentGraph 是两条不同入口，互不污染。

## 四、AgentRuntime 模块

文件：`internal/agent/runtime/*.go`

职责：

- 提供通用 Agent 注册和运行能力。
- `Registry` 保存不同 Agent 实例。
- `Runtime.Run` 根据 `agent_id` 找到具体 Agent。
- 自动补全默认 `request_id`。
- `AddTraceFields` 给 Agent SSE payload 注入：
  - `requestId`
  - `request_id`
  - `agent_id`
  - `trace_id`

当前默认 Agent：

```text
smartinsure-advisor
```

这层不做保险业务判断，只做 Agent 调度和追踪字段管理。

## 五、SmartInsureAdvisorAgent 适配模块

文件：`internal/agent/smartinsureagent/agent.go`

职责：

- 实现 `runtime.Agent` 接口。
- 将 `agentruntime.AgentRequest` 转成 `chatflow.Request`。
- 调用 `AgentGraph.Run`。
- 给所有从 Graph 返回的事件追加 trace 字段。
- 保持业务决策下沉到 Graph，不在 Agent adapter 里做规划。

可以理解为：

```text
AgentRuntime 的标准协议
  -> SmartInsureAdvisorAgent adapter
  -> 保险专用 AgentGraph
```

## 六、AgentGraph 主循环模块

文件：`internal/agent/smartinsureagent/graph.go`

职责：

- 承载 Plan-Act 主循环。
- 维护最大轮次 `AGENT_MAX_ITERATIONS`。
- 控制每个工具超时 `AGENT_TOOL_TIMEOUT`。
- 执行 action 并把结果写入 observation。
- 决定何时继续 replan，何时 final answer。

核心流程：

```text
session_validate
  -> memory_load
  -> reasoner.Next
  -> validateDecision
  -> duplicate action guard
  -> executeAction
  -> append observation
  -> replan / finalAnswer / fallback
```

### 6.1 session_validate

作用：

- 如果传了 `chat_session_id`，必须同时有 `anonymous_id` 或 `user_id`。
- 避免没有身份的客户端访问/污染会话数据。

### 6.2 memory_load

作用：

- Graph 侧不直接访问数据库。
- API 层已经读取并裁剪历史消息。
- Graph 只使用 `state.History`。

### 6.3 reasoner.Next

作用：

- 决定下一步 action。
- 生产模式优先使用 LLM JSON planner。
- 没有可用 LLM 或 JSON 失败时，回退 heuristic reasoner。

### 6.4 action_validate

作用：

- 只允许白名单 action。
- 拒绝额外字段、非字符串、显式 `null`。
- `final_answer.answer_text` 只允许内部可信 reasoner 使用。

### 6.5 duplicate action guard

作用：

- 拦截同一工具和同一输入的重复调用。
- 写入 observation：`重复工具调用已拦截`。
- 要求 reasoner 基于已有 observation 重新规划。
- 避免模型反复调用同一个工具导致空转。

### 6.6 tool executor

作用：

- 根据 action 调用不同工具：
  - `product_search`
  - `knowledge_search`
  - `product_detail`
- 工具调用统一受 timeout 控制。
- 工具结果会裁剪为 observation。

### 6.7 final answer

作用：

- 将用户原始问题、`answer_brief`、产品卡片、steps observation 注入最终回答上下文。
- 调用既有 AnswerStreamer 流式输出。
- 输出 `sources/disclaimer/done`。

## 七、AgentState 状态模块

文件：`internal/agent/smartinsureagent/state.go`

职责：

- 保存一次 Agent 请求内的运行状态。
- 是 Plan-Act 的 scratchpad 容器。

核心字段：

- `Request`：本次请求。
- `Events`：SSE 输出通道。
- `History`：短期记忆，由 API 层加载。
- `Intent`：意图识别结果。
- `Steps`：每轮 action、input、observation、错误和耗时。
- `Products`：可展示产品卡片。
- `Results`：知识检索结果。
- `Sources`：最终可展示来源。
- `Iteration`：当前循环轮次。

重要方法：

- `appendStep`：写入一轮 scratchpad。
- `hasAction`：判断某 action 是否成功执行过。
- `hasAttemptedAction`：判断某 action 是否尝试过，包括失败。
- `hasAttemptedActionWithInput`：判断同一工具同一输入是否已尝试，用于重复调用防护。
- `emit`：统一向 SSE channel 写事件，并尊重 context cancellation。

## 八、Action 校验模块

文件：`internal/agent/smartinsureagent/actions.go`

职责：

- 定义可用 action。
- 校验模型或 heuristic 输出的 action JSON。
- 生成重复调用 fingerprint。

允许 action：

| Action | 用途 | 主要输入 |
|---|---|---|
| `product_search` | 搜索保险产品卡片 | `query` |
| `knowledge_search` | 检索保险知识/条款来源 | `query` |
| `product_detail` | 解析指定产品详情 | `product_url/product_name` |
| `ask_followup` | 追问用户补充信息 | `question` |
| `final_answer` | 输出最终回答 | `answer_brief` |

校验规则：

- action 必须在白名单中。
- `action_input` 只允许 schema 中声明的字段。
- 字段值必须是字符串。
- 显式 `null` 会被拒绝。
- 工具查询缺失时可从原始用户 message 回填。
- `product_detail.product_url` 最终必须存在。
- 模型 planner 不允许输出 `answer_text` 直接绕过最终回答链路。

## 九、Reasoner / Planner 模块

文件：`internal/agent/smartinsureagent/planner.go`

职责：

- 实现“下一步该做什么”的推理逻辑。
- 同时支持 LLM JSON planner 和 deterministic heuristic fallback。

### 9.1 LLM JSON planner

生产模式下，如果 `agent_planner` stage 有可用模型配置：

```text
reasoner = modelReasoner
```

它会把以下信息放入 prompt：

- 用户问题。
- 近期对话。
- 当前意图。
- 已展示产品。
- 知识来源。
- scratchpad observations。
- 可用 action 列表。
- 不重复工具输入的约束。
- 合规要求。

模型只能输出 JSON：

```json
{
  "thought": "简短规划理由",
  "action": "knowledge_search",
  "action_input": {
    "query": "等待期 条款 保险"
  }
}
```

### 9.2 JSON repair

如果模型输出不是合法 JSON：

- 当 `AGENT_ACTION_REPAIR_ENABLED=true` 时，会追加一次修复提示。
- 修复后仍失败，回退 heuristic reasoner。

### 9.3 heuristic reasoner

用途：

- 本地无 LLM key 时仍能跑通。
- LLM 异常时保证 Agent 不直接失败。
- 单元测试可稳定验证。

行为：

- 超出保险范围：直接 `final_answer` 边界说明。
- 信息不足：`ask_followup`。
- 泛化推荐，如“给我推荐保险”：先追问年龄、预算、偏好。
- 产品类问题：优先 `product_search`。
- 知识/条款类问题：`knowledge_search`。
- 工具已经尝试过：不重试同一 action，转向下一步或 final answer。

## 十、Tools 工具封装模块

文件：`internal/agent/smartinsureagent/tools.go`

职责：

- 将底层 chatflow 能力封装成 Agent tool。
- 把工具原始结果转换成简短 observation，避免 scratchpad 过长。

当前工具：

### 10.1 ProductSearch

底层接口：

```text
chatflow.ProductSearcher
```

输出：

- `Products`：前端可展示产品卡片。
- `Summary`：如 `产品搜索返回 10 个候选产品。`
- observation data：
  - `product_count`
  - `products` 产品名称列表

### 10.2 KnowledgeSearch

底层接口：

```text
chatflow.FallbackSearcher
```

输出：

- `Results`：检索结果。
- `Sources`：去重后的来源。
- `Summary`：如 `知识检索返回 1 条来源。`
- observation data：
  - `source_count`
  - `sources` 来源标题列表

### 10.3 ProductDetail

底层接口：

```text
chatflow.DetailRunner
```

实现位置主要在 `graph.go` 中，因为它需要同时处理：

- 直达产品详情按钮。
- planner 选择的 product_detail。
- `detail_items/delta/done` 事件转发。
- detail observation 收集。
- tool timeout。

## 十一、产品详情两种模式

### 11.1 前端按钮直达详情

触发条件：

```text
action=product_detail 或 product_followup
```

行为：

- 不让 planner 猜。
- 直接执行详情工具。
- 详情工具输出 `detail_items/delta/done`。
- 适合用户点击“AI 解析”按钮后快速看到详情。

### 11.2 planner 选择 product_detail

触发条件：

```text
reasoner.Next -> action=product_detail
```

行为：

- 执行详情工具。
- `detail_items` 可展示给前端。
- 中间 `delta` 不直接输出给用户，避免工具阶段和最终回答重复。
- 将 detail 统计写入 observation。
- 回到下一轮 reasoner，再由 `final_answer` 统一收口。

## 十二、SSE 协议模块

Agent 模式继续兼容现有事件：

| 事件 | 用途 |
|---|---|
| `status` | 当前处理阶段 |
| `products` | 产品卡片 |
| `detail_items` | 产品详情保障项 |
| `delta` | 流式文本 |
| `sources` | 来源 |
| `disclaimer` | 免责声明 |
| `done` | 结束 |
| `error` | 错误 |

Agent 新增/强化的 `status.stage`：

| stage | 含义 |
|---|---|
| `reasoning` | 正在规划下一步 |
| `tool_running` | 正在执行工具 |
| `observing` | 已读取工具结果或拦截重复调用 |
| `answering` | 正在生成最终回答 |

注意：

- `thought` 不会输出给前端。
- `agent_id/trace_id` 只在 `/api/agent/chat` 出现。
- `/api/chat` 不应出现 Agent trace 字段。

## 十三、配置模块

文件：

- `internal/config/config.go`
- `configs/llm_providers.yaml`

关键配置：

| 配置 | 默认值 | 说明 |
|---|---|---|
| `AGENT_CHAT_ENABLED` | `true` | 是否启用 `/api/agent/chat` |
| `AGENT_DEFAULT_ID` | `smartinsure-advisor` | 默认 Agent ID |
| `AGENT_TRACE_ENABLED` | `true` | 是否输出 trace_id |
| `AGENT_MODE` | `plan_act` | Agent 模式 |
| `AGENT_MAX_ITERATIONS` | `4` | 最大 Plan-Act 轮次 |
| `AGENT_TOOL_TIMEOUT` | `15` | 单工具超时秒数 |
| `AGENT_ACTION_REPAIR_ENABLED` | `true` | 是否启用 JSON repair |
| `AGENT_SCRATCHPAD_MAX_CHARS` | `6000` | planner 输入最大字符 |
| `AGENT_OBSERVATION_MAX_CHARS` | `2000` | 单条 observation 最大字符 |

`configs/llm_providers.yaml` 中新增：

```yaml
routing:
  agent_planner:
    provider: minimax
```

如果没有可用 provider key，系统自动回退 heuristic reasoner。

## 十四、测试模块

文件：

- `internal/agent/smartinsureagent/actions_test.go`
- `internal/agent/smartinsureagent/planner_test.go`
- `internal/agent/smartinsureagent/graph_test.go`
- `internal/api/router_test.go`

覆盖点：

- action 白名单。
- action_input schema。
- 非字符串和显式 `null` 拒绝。
- planner JSON 解析和 repair。
- Plan-Act 正常链路。
- thought 不泄露。
- ask_followup 不调用工具。
- max iteration fallback。
- 重复工具调用拦截。
- product_detail timeout 和 observation。
- planner product_detail replan。
- `/api/chat` 不输出 `agent_id/trace_id`。
- `/api/agent/chat` 不调用旧 workflow runner。

常用验证命令：

```bash
cd /home/zhaoting/Agent/smartinsure-eino-backend
GOCACHE=/tmp/smartinsure-go-build-cache go test -count=1 ./internal/agent/smartinsureagent ./internal/api ./internal/config
GOCACHE=/tmp/smartinsure-go-build-cache go test -count=1 ./...
```

## 十五、当前运行验证

当前后端 Agent 服务监听：

```text
0.0.0.0:34567
```

前端内网访问：

```text
http://192.168.2.33:3000/chat/agent
```

典型冒烟：

```bash
curl -N -H 'Content-Type: application/json' \
  -d '{"message":"给我推荐保险","requestId":"smoke-agent-followup"}' \
  http://127.0.0.1:34567/api/agent/chat
```

期望：

- 泛化推荐先 `ask_followup`。
- SSE 包含 `agent_id/trace_id`。
- 最终 `done`。

```bash
curl -N -H 'Content-Type: application/json' \
  -d '{"message":"百万医疗险怎么选？","requestId":"smoke-agent-specific"}' \
  http://127.0.0.1:34567/api/agent/chat
```

期望：

- 出现 `reasoning/tool_running/observing/answering`。
- 返回 `products`。
- 返回 `sources/disclaimer/done`。

## 十六、维护建议

新增 Agent 能力时优先遵守以下规则：

- 先扩展 action schema，再接工具。
- 新工具必须有 timeout。
- 新工具结果必须裁剪成 observation。
- 不允许前端参与 planner 决策。
- 不允许 thought 输出到 SSE。
- `/api/chat` 旧链路不受 Agent 配置影响。
- 每个新 action 至少补：
  - schema test
  - graph action test
  - SSE contract test
  - error/fallback test
