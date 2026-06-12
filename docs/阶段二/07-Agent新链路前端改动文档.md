# Agent 新链路前端改动文档

状态：方案设计中  
适用范围：前端聊天页、聊天 API 客户端、SSE 消费、会话恢复、产品卡片展示  
关联后端文档：`08-Agent新链路后端改动文档.md`

## 一、背景

当前前端主要对接已有 `/api/chat` 链路。后端计划在不影响旧链路的前提下，新增一条 Agent 承载链路，对外提供新的 Agent Chat 接口。

本次前端改动目标不是重做聊天页面，而是在现有聊天体验上增加一套可切换的新接口调用能力：

```text
旧链路：/api/chat
新链路：/api/agent/chat
```

旧链路继续作为稳定入口和回滚路径，新链路用于验证 Agent Graph、Agent Runtime、Tool 调用和短期记忆能力。

## 二、目标

1. 前端支持通过配置切换旧 `/api/chat` 与新 `/api/agent/chat`。
2. 新链路继续复用现有聊天 UI、SSE 渲染、产品卡片和来源展示。
3. 新链路请求必须携带 `anonymous_id` 与 `chat_session_id`。
4. 新链路 SSE 事件兼容旧链路的核心事件，降低前端改造成本。
5. 为后续展示 Agent 状态、Tool 调用过程、Trace 信息预留扩展字段。

## 三、非目标

1. 不重做聊天页面布局。
2. 不在前端实现 Agent 规划逻辑。
3. 不在前端保存完整聊天历史，历史仍以服务端为准。
4. 不要求第一版展示完整 Agent 思考过程。
5. 不替换旧 `/api/chat`，旧接口继续保留。

## 四、接口切换设计

### 4.1 推荐配置

前端增加一个聊天接口模式配置：

```ts
type ChatBackendMode = "legacy_chat" | "agent_chat"
```

建议通过环境变量控制：

```text
NEXT_PUBLIC_CHAT_BACKEND_MODE=legacy_chat
NEXT_PUBLIC_AGENT_CHAT_URL=/api/agent/chat
NEXT_PUBLIC_LEGACY_CHAT_URL=/api/chat
```

默认仍使用 `legacy_chat`，只有明确开启时才调用新链路。

### 4.2 路由映射

| 模式 | 请求地址 | 说明 |
|---|---|---|
| `legacy_chat` | `/api/chat` | 当前稳定链路 |
| `agent_chat` | `/api/agent/chat` | 新 Agent 链路 |

## 五、请求体改动

新链路请求体建议：

```json
{
  "anonymous_id": "anon_xxx",
  "chat_session_id": "chat_xxx",
  "message": "百万医疗险怎么选？",
  "action": "",
  "product_url": "",
  "product_name": "",
  "stream": true,
  "metadata": {
    "source": "web"
  }
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `anonymous_id` | 匿名用户必填 | 浏览器本地匿名身份 |
| `chat_session_id` | 必填 | 当前聊天会话 |
| `message` | 普通聊天必填 | 用户输入文本 |
| `action` | 否 | `product_detail` / `product_followup` 等动作 |
| `product_url` | 商品详情场景必填 | 当前选中产品链接 |
| `product_name` | 商品详情场景建议传 | 当前选中产品名称 |
| `stream` | 否 | 第一版固定为 `true` |
| `metadata` | 否 | 前端来源、页面信息、实验标识 |

兼容要求：

1. 普通聊天时，前端只需要传 `message`、`anonymous_id`、`chat_session_id`。
2. 点击产品详情时，前端传 `action=product_detail`、`product_url`、`product_name`。
3. 产品追问时，前端传 `action=product_followup`、`product_url`、`message`。

## 六、SSE 事件兼容

第一版新链路必须兼容旧链路核心事件：

| 事件 | 前端行为 |
|---|---|
| `status` | 更新当前加载状态 |
| `products` | 渲染产品卡片 |
| `detail_items` | 渲染产品详情条目 |
| `delta` | 追加 assistant 流式文本 |
| `sources` | 渲染来源链接 |
| `disclaimer` | 渲染免责声明 |
| `done` | 结束当前回复 |
| `error` | 显示错误并结束当前回复 |

新链路可以在 data 中增加可选字段：

```json
{
  "agent_id": "smartinsure-advisor",
  "stage": "searching",
  "trace_id": "trace_xxx",
  "message": "正在搜索保险产品..."
}
```

前端处理原则：

1. 已知字段正常消费。
2. 未知字段保留但不阻断渲染。
3. 未知事件第一版可以忽略，并在开发环境打印调试日志。

## 七、前端模块改动

建议新增或调整以下模块：

| 模块 | 改动 |
|---|---|
| `chat-api` | 根据模式选择 `/api/chat` 或 `/api/agent/chat` |
| `chat-stream` | 复用 SSE 解析，允许 data 中出现 `agent_id`、`trace_id` |
| `chat-session` | 确保发送前已有 `anonymous_id` 与 `chat_session_id` |
| `chat-store` | 保存当前请求模式、流式状态、产品卡片、来源、错误 |
| `product-card` | 复用现有产品卡片结构，不因新链路改 UI |
| `debug-panel` | 可选，开发环境展示 `trace_id`、`agent_id`、`stage` |

建议文件组织：

```text
apps/frontend/
  src/
    lib/
      chat-api.ts
      chat-stream.ts
      chat-session.ts
    stores/
      chat-store.ts
    components/
      chat/
        ChatPanel.tsx
        ProductCards.tsx
        Sources.tsx
```

如果当前前端目录结构不同，按现有结构等价落位即可。

## 八、页面交互改动

第一版页面交互保持不变：

```text
用户输入
  -> 前端追加 user message
  -> 调用当前模式对应接口
  -> 消费 SSE
  -> products 事件渲染产品卡
  -> delta 事件追加回答
  -> done 后解除输入锁定
```

可选增强：

1. 开发环境显示当前链路模式：`legacy_chat` / `agent_chat`。
2. 开发环境显示 `trace_id`，便于和后端日志对齐。
3. Agent 链路失败时，前端可提示“新链路暂不可用”，不自动静默切旧链路，避免验证数据混乱。

## 九、错误处理

| 场景 | 前端处理 |
|---|---|
| `/api/agent/chat` 404 | 提示新链路未部署 |
| 返回 `error` event | 显示错误消息，结束当前流 |
| SSE 中断 | 标记 assistant 回复失败，可允许重试 |
| session 无效 | 重新获取当前 session，再提示用户重试 |
| Agent 超时 | 显示超时提示，不清空已有消息 |

## 十、测试用例

前端需要覆盖：

1. `legacy_chat` 模式仍可正常聊天。
2. `agent_chat` 模式可正常消费 `status/products/delta/sources/disclaimer/done`。
3. 产品卡片字段完整展示：名称、价格、平台、标签、简介、跳转链接。
4. 商品详情和商品追问事件能正常渲染。
5. SSE 中断、error event、接口 500 时 UI 状态能恢复。
6. 刷新页面后仍能通过 `chat_session_id` 恢复历史。

## 十一、验收标准

1. 不开启 `agent_chat` 时，旧 `/api/chat` 行为不变。
2. 开启 `agent_chat` 后，同一批 6 角色测试用例前端可完整渲染。
3. 产品卡片、来源、免责声明、流式文本均能正确显示。
4. 前端发送请求时稳定携带 `anonymous_id` 与 `chat_session_id`。
5. 新旧链路切换不需要改页面业务代码，只改配置或 API client。
