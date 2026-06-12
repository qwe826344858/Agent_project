# 前端 RAG Agent 页面接入说明

状态：前端适配方案，待实施  
更新时间：2026-06-11  
关联后端：`/chat/rag-agent`、`/api/chat/rag-agent`

## 一、目标

前端新增一条独立的 RAG Agent 聊天页面，让用户基于已入库的产品向量知识库进行咨询和产品匹配。

本文件只输出前端适配方案，不包含前端代码改动。后续实施时应复用现有聊天页、SSE 解析和产品卡片能力，不重做 UI。

## 二、最新后端协议结论

RAG Agent 已调整为返回产品卡片事件：

```text
event: products
```

因此前端展示策略应与原产品推荐一致：

1. 收到 `products` 后，复用现有产品卡片/吸顶产品面板展示。
2. 收到 `sources` 后，只作为 RAG 召回依据、引用来源或兜底链接展示。
3. 不应只依赖 `sources` 给用户展示产品链接。

## 三、页面入口

建议新增页面：

```text
/chat/rag-agent
```

页面复用现有：

| 能力 | 说明 |
| --- | --- |
| `ChatPageShell` | 聊天页面外壳 |
| SSE parser | 继续消费后端流式事件 |
| 产品卡片组件 | 继续消费 `products.items` |
| 来源展示组件 | 继续消费 `sources.items` |
| 会话恢复 | 继续传 `anonymous_id` 和 `chat_session_id` |

页面差异：

| 项目 | 建议配置 |
| --- | --- |
| 后端模式 | `rag_agent_chat` |
| 页面标识 | `RAG Agent` |
| 空状态标题 | `想从产品库里匹配什么保障？` |
| 空状态说明 | `基于已入库产品知识库召回责任、标签和来源` |

## 四、接口配置

建议新增环境变量：

```text
NEXT_PUBLIC_RAG_AGENT_CHAT_URL=/chat/rag-agent
```

默认请求地址：

```text
POST /chat/rag-agent
```

如果部署侧统一走 `/api` 前缀，也可以配置为：

```text
NEXT_PUBLIC_RAG_AGENT_CHAT_URL=/api/chat/rag-agent
```

## 五、请求格式

RAG Agent 复用 Agent/DeepAgent 的请求体结构：

```json
{
  "message": "帮我匹配适合家庭投保、保障高端的百万医疗险",
  "anonymous_id": "anon_xxx",
  "chat_session_id": "chat_xxx",
  "stream": true,
  "metadata": {
    "source": "web"
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `message` | 用户输入的问题或产品匹配需求 |
| `anonymous_id` | 浏览器匿名用户 ID |
| `chat_session_id` | 当前聊天会话 ID |
| `stream` | 固定使用流式输出 |
| `metadata.source` | 固定为 `web`，便于后端日志定位 |

## 六、SSE 事件

RAG Agent 页面应继续消费已有 SSE 事件：

| 事件 | 前端行为 |
| --- | --- |
| `status` | 更新当前执行状态 |
| `products` | 展示 RAG 召回后的产品卡片 |
| `sources` | 展示 RAG 召回依据和来源 |
| `delta` | 追加助手回答文本 |
| `disclaimer` | 展示免责声明 |
| `error` | 展示错误消息并结束流式状态 |
| `done` | 结束本次回复 |

推荐渲染优先级：

1. `products`：用户可点击的产品卡片，是主展示内容。
2. `delta`：模型解释为什么推荐这些产品。
3. `sources`：辅助展示召回依据，不替代产品卡片。

## 七、`products` 事件格式

后端会把 RAG 召回结果转换成现有产品卡片结构：

```text
event: products
data: {
  "items": [
    {
      "id": "rag_a3cb2c798a6b",
      "name": "众民保·百万医疗险2025（家庭版）——转保版 臻选版",
      "company": "huize",
      "price": null,
      "price_label": "详见产品页",
      "tags": ["医疗险", "家庭", "外购药", "质子重离子", "住院医疗"],
      "url": "https://www.huize.com/apps/cps/index/product/detail?DProtectPlanId=107830&planId=107830&prodId=103583",
      "platform": "huize",
      "brief": "产品名称：... 保障责任：特定药品医疗保险金 ..."
    }
  ]
}
```

前端处理要求：

| 字段 | 前端用途 |
| --- | --- |
| `id` | 卡片 key |
| `name` | 产品名称 |
| `company` | 公司/平台展示，可为空 |
| `price_label` | 价格占位，RAG 产品通常为 `详见产品页` |
| `tags` | 卡片标签 |
| `url` | 产品详情跳转链接，必须用于点击跳转 |
| `platform` | 平台标识 |
| `brief` | 卡片摘要 |

注意：

1. `products.items[].url` 是产品卡片跳转主字段。
2. RAG 卡片的 `id` 使用 `rag_` 前缀，前端不需要特殊处理。
3. 如果 `price` 为 `null`，前端展示 `price_label` 即可。
4. 点击“查看保障详情”仍可复用现有 `product_detail` 交互，传入卡片的 `url` 和 `name`。

## 八、`sources` 事件格式

`sources` 仍会返回，但定位是召回依据：

```text
event: sources
data: {
  "items": [
    {
      "title": "众民保·百万医疗险2025（家庭版）——转保版 臻选版 - 特定药品医疗保险金",
      "url": "https://www.huize.com/apps/cps/index/product/detail?DProtectPlanId=107830&planId=107830&prodId=103583",
      "site": "huize",
      "product_url": "https://www.huize.com/apps/cps/index/product/detail?DProtectPlanId=107830&planId=107830&prodId=103583"
    }
  ]
}
```

前端处理建议：

1. 来源列表继续展示 `title`、`site`、`url`。
2. 如需要从来源反查产品链接，优先使用 `product_url`，其次使用 `url`。
3. 不要只用 `sources` 来生成产品卡片，产品卡片以 `products.items` 为准。

## 九、推荐问题

RAG Agent 页面建议使用场景化兜底推荐问题：

```text
帮我匹配适合家庭投保、保障高端的百万医疗险
外购药保障强的百万医疗险有哪些？
适合少儿的中高端医疗险怎么选？
重疾险里性价比高的个人方案有哪些？
有哪些产品支持特需医疗？
```

如果后端 `/api/suggestions` 正常返回推荐问题，仍可优先展示后端结果；如果接口为空或失败，则使用上述 RAG Agent 兜底问题。

## 十、建议代码改动

| 文件 | 建议改动 |
| --- | --- |
| `apps/frontend/src/lib/api.ts` | 新增 `rag_agent_chat` 模式和 `NEXT_PUBLIC_RAG_AGENT_CHAT_URL` |
| `apps/frontend/src/components/ChatPageShell.tsx` | 支持 RAG 页面自定义空状态标题、说明和兜底推荐问题 |
| `apps/frontend/src/app/chat/rag-agent/page.tsx` | 新增 RAG Agent 页面入口 |
| `apps/frontend/src/lib/__tests__/api.test.ts` | 补充 RAG Agent 默认地址、配置覆盖和请求体单测 |

如果当前 `ChatPageShell` 已经支持 `products` 事件并更新产品面板，则无需新增产品卡片渲染逻辑，只需要让 RAG 页面走新的后端模式。

## 十一、验证方式

后端 smoke 验证：

```bash
curl -sS --max-time 60 -N \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我匹配外购药保障强的百万医疗险","requestId":"rag-products-smoke","stream":true}' \
  http://127.0.0.1:34567/chat/rag-agent
```

前端单测：

```bash
cd /home/zhaoting/Agent/Agent_project/apps/frontend
npm test -- --runInBand src/lib/__tests__/api.test.ts
```

前端构建：

```bash
cd /home/zhaoting/Agent/Agent_project/apps/frontend
npm run build
```

浏览器验证：

```text
http://<frontend-host>:<frontend-port>/chat/rag-agent
```

验收点：

1. 页面顶部展示 `RAG Agent` 标识。
2. 空状态展示 RAG 场景化标题和推荐问题。
3. 发送问题后请求 `/chat/rag-agent` 或配置的 `NEXT_PUBLIC_RAG_AGENT_CHAT_URL`。
4. 能收到并渲染 `products` 产品卡片。
5. 产品卡片点击使用 `products.items[].url` 跳转。
6. 能收到并展示 `sources`，且 `sources.items[].product_url` 可作为来源产品链接。
7. 能正常渲染 `status`、`delta`、`disclaimer`、`error`、`done`。
8. 不影响 `/`、`/chat/agent`、`/chat/deep-agent` 原有页面。

## 十二、前端实现注意事项

1. RAG Agent 产品来自向量库召回，不会主动平台搜索，也不会主动抓新产品详情页。
2. RAG Agent 首屏回答可能先返回 `status` 和 `products`，再持续返回 `delta`，前端不要等待回答全文结束后才展示卡片。
3. 如果一次召回多个 chunk 属于同一产品，后端已经按产品链接去重，前端不需要二次按 chunk 去重。
4. 如果 `products.items` 为空但 `sources.items` 非空，说明本次召回缺少可用产品链接，前端可以只展示来源和文本回答。
5. 后续如果支持“查看保障详情”，复用已有产品卡片动作即可，入参为 `productUrl=url`、`productName=name`。
