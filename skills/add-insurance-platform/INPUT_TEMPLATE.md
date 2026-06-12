# 新增保险平台 — 输入模板

请复制以下模板，填写后提供给我，我将自动生成代码、注册平台、编写测试并验证。

---

## 最小输入（只需 3 项）

```
【平台名称】（必填）如：众安保险
【平台域名】（必填）如：zhongan.com
【认证方式】（必填）无需认证 / 需要Cookie(环境变量名) / 需要API Key(环境变量名)

【curl 示例】（强烈推荐，粘贴完整 curl 命令）
curl -X POST 'https://api.example.com/search' \
  -H 'Content-Type: application/json' \
  -H 'Referer: https://www.example.com' \
  -d '{"keyword":"医疗","page":1}'

【响应示例】（强烈推荐，粘贴接口返回的 JSON 片段，至少含 1 个产品）
{
  "code": 0,
  "data": {
    "list": [
      {
        "title": "xxx百万医疗险",
        "price": 16800,
        "url": "https://www.example.com/product/123",
        "company": "xxx保险",
        "desc": "最高600万保额"
      }
    ]
  }
}
```

---

## 完整输入（字段映射不明确时使用）

```
【平台名称】
【平台域名】
【接口地址】完整 URL
【请求方式】GET / POST
【请求格式】query-string / form-data / json
【认证方式】无需认证 / 需要Cookie(环境变量名) / 需要API Key(环境变量名) / 其他(说明)

【curl 示例】
curl ...

【响应示例】
{ ... }

【字段映射】（可选，格式清晰时自动推断）
  - 产品名称：data.list[].title
  - 产品价格：data.list[].price（单位：元 / 分）
  - 产品链接：data.list[].url
  - 保险公司：data.list[].company（如无，从产品名提取）
  - 产品简介：data.list[].desc
  - 标签分类：data.list[].category
  - 分页参数：page（从 1 开始）

【特殊说明】（可选）
  - 如：价格单位是分，需除以 100
  - 如：Referer 中文需 URL 编码
  - 如：需要特殊 User-Agent
  - 如：搜索关键词需要额外映射
```

---

## 填写说明

| 字段 | 必填 | 说明 |
|---|---|---|
| 平台名称 | ✅ | 中文名，用于前端卡片展示 |
| 平台域名 | ✅ | 主域名，用于代码标识 |
| 认证方式 | ✅ | 决定是否需要配置环境变量 |
| curl 示例 | 推荐 | 从中自动解析 headers、body、请求方式 |
| 响应示例 | 推荐 | 从中自动推断字段映射 |
| 字段映射 | 可选 | 响应结构复杂时手动指定 |
| 特殊说明 | 可选 | 价格单位转换、编码、特殊 headers 等 |

> 提供 curl + 响应示例即可覆盖 90% 场景，其余信息自动推断。
