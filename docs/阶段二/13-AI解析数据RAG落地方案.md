# AI 解析数据 RAG 落地方案

状态：方案准备  
更新时间：2026-06-04  
关联后端：`/home/zhaoting/Agent/smartinsure-eino-backend`

## 一、本次验证结论

已验证当前 AI 解析链路可以从产品详情页提取结构化保障责任，返回事件为 `detail_items`。

验证请求：

```bash
curl -sS --max-time 180 -N \
  -H 'Content-Type: application/json' \
  -d '{"action":"product_detail","productUrl":"https://www.huize.com/apps/cps/index/product/detail?DProtectPlanId=108504&prodId=104006&planId=108504&_rag_check=20260604","productName":"复星联合星相守2号长期医疗保险（个人版）","requestId":"rag-detail-uncached-check"}' \
  http://127.0.0.1:34567/api/chat
```

实际返回的结构化数据：

- 产品：复星联合星相守2号长期医疗保险（个人版）
- 保障责任数量：13
- 字段结构：`name`、`coverage`、`description`、`is_optional`
- 必选责任：7 项
- 可选责任：6 项

已提取的责任项：

| 类型 | 责任名称 | 额度/范围 | 说明摘要 |
| --- | --- | --- | --- |
| 必选 | 一般住院医疗保险金 | 详见条款 | 一般疾病住院医疗费用 |
| 必选 | 轻重症疾病住院医疗保险金 | 详见条款 | 轻症、中症住院医疗费用 |
| 必选 | 重大疾病住院医疗保险金 | 详见条款 | 重大疾病住院治疗费用 |
| 必选 | 恶性肿瘤-重度基因检测费用医疗保险金 | 详见条款 | 癌症基因检测费用 |
| 必选 | 住院期间外购药品及外购医疗器械费用医疗保险金 | 详见条款 | 住院期间处方外购药品和器械 |
| 必选 | 重大疾病关爱保险金 | 详见条款 | 首次确诊重疾一次性给付 |
| 必选 | 健康管理服务 | 含服务 | 健康咨询、档案、就医绿色通道等 |
| 可选 | 重大疾病康复医疗保险金 | 详见条款 | 重疾治疗后的康复费用 |
| 可选 | 重大疾病住院或重症监护病房住院津贴保险金 | 详见条款 | 按日给付住院或 ICU 津贴 |
| 可选 | 恶性肿瘤特定药品费用医疗保险金 | 详见条款 | 癌症特定药品费用 |
| 可选 | 重大疾病补充关爱保险金 | 10万/20万 | 额外给付补充关爱金 |
| 可选 | 重大疾病住院拓展特需医疗保险金 | 详见条款 | 特需病房、国际部等高端医疗区域费用 |
| 可选 | 基础医疗保险金 | 详见条款 | 基础医疗保障 |

同时确认一个链路行为：

- `/api/agent/chat` 直连详情页时出现过 `context deadline exceeded`，原因是 Agent 工具默认超时时间较短。
- `/api/chat` 普通详情链路可成功返回 `detail_items`。
- 后端已补充缓存命中时继续返回 `detail_items`，避免“已经解析过但前端拿不到结构化数据”的问题。

## 二、策略调整：先处理平台异构

不同平台的产品页结构不会一致，不能假设 AI 解析出来的数据天然统一。正确策略应拆成三层：

1. 平台原始抽取层：保留每个平台页面里抽出来的原始字段、原始块、证据片段和置信度。
2. 标准化归一层：把不同平台的字段映射到统一的产品责任模型，缺失字段明确标为 `unknown`，不能让模型补猜。
3. RAG 知识层：只对标准化后的责任知识做 embedding，同时在 metadata 中保留平台来源、原始字段名和证据。

也就是说，RAG 不应该直接依赖某个平台的页面格式，而应该依赖统一后的 canonical schema。

当前后端已有的 `ProductDetail` 可以作为前端展示的最小结构：

```json
{
  "product_name": "产品名",
  "product_url": "产品链接",
  "platform": "平台",
  "duties": [
    {
      "name": "保障责任名",
      "coverage": "额度/范围",
      "description": "责任说明",
      "is_optional": false
    }
  ],
  "cn_char_count": 12345,
  "match_rate": 0.8
}
```

但 RAG 入库时建议扩展成更完整的内部标准结构：

```json
{
  "product_key": "huize:104006:108504",
  "platform": "huize",
  "platform_label": "慧择",
  "source_url": "规范化产品URL",
  "product_name": "标准产品名",
  "raw_product_name": "平台页面原始产品名",
  "product_type": "medical",
  "product_type_label": "医疗险",
  "raw_tags": ["中高端医疗", "保证续保"],
  "standard_tags": [
    {
      "category": "positioning",
      "code": "high_end",
      "label": "高端",
      "source": "rule|platform|llm",
      "confidence": 0.82
    },
    {
      "category": "audience",
      "code": "family",
      "label": "家庭",
      "source": "rule|platform|llm",
      "confidence": 0.76
    }
  ],
  "plans": [
    {
      "plan_id": "108504",
      "plan_name": "计划一",
      "duties": [
        {
          "duty_id": "sha256(product_key + raw_name)",
          "raw_name": "平台原始责任名",
          "canonical_name": "标准化责任名",
          "category": "inpatient_medical",
          "coverage_text": "页面原文中的额度/范围",
          "deductible_text": "免赔额，未知则 unknown",
          "reimbursement_text": "赔付比例，未知则 unknown",
          "waiting_period_text": "等待期，未知则 unknown",
          "option_type": "required|optional|unknown",
          "description": "标准化后的责任说明",
          "evidence": ["来自页面的原文片段"],
          "confidence": 0.86
        }
      ]
    }
  ]
}
```

这样比直接把网页原文切块更适合 RAG，原因是：

1. 检索粒度更稳定：用户问“外购药能不能报”，可以直接命中“外购药品及外购医疗器械费用”这个责任 chunk。
2. 元数据更丰富：可以按产品 URL、平台、可选/必选、责任名称过滤。
3. 平台差异可控：慧择可能有 planId，平安可能是 hash 路由，小雨伞可能是活动页；最终都归一到 `product_key + plan_id + duty_id`。
4. 去重更容易：同一个标准产品键只保留一份最新标准化结果，同时可保留多个原始 URL。
5. 生成答案更可靠：模型拿到的是干净结构化责任，不是夹杂导航、脚本、营销文案的网页原文。

## 三、平台适配策略

### 1. 平台识别

先根据 URL 和页面特征识别平台：

| 平台 | 识别依据 | 重点字段 |
| --- | --- | --- |
| 慧择 | `huize.com`、`prodId`、`planId`、`DProtectPlanId` | 产品 ID、计划 ID、责任列表、可选责任 |
| 平安 | `pingan.com`、hash 路由、页面内产品编码 | 产品编码、计划/版本、条款 PDF 或页面保障表 |
| 小雨伞 | `xiaoyusan.com` 或其活动页域名 | 活动页产品名、保障计划、责任说明 |
| 通用页面 | 无法识别的平台 | 只抽取有证据的责任字段 |

### 2. 平台 Adapter 与解析模板

后端必须增加平台 adapter，而不是一个 prompt 解析所有页面。整体顺序是：

```text
DetectPlatform(url, cleanedText)
  -> platform = huize / pingan / xiaoyusan / generic
  -> LoadPlatformTemplate(platform)
  -> HuizeTemplate / PinganTemplate / XiaoyusanTemplate / GenericTemplate
  -> PlatformRawExtract
  -> CanonicalNormalizer
  -> ProductDetail + RAGDocument
```

这里的 `platform` 不是由 LLM 随便生成的标签，而是由后端平台识别器确定。不同平台进入不同解析方案模板：

| platform | 展示名 | 解析器 | 解析模板 | 重点解析内容 |
| --- | --- | --- | --- | --- |
| `huize` | 慧择 | `HuizeExtractor` | `huize_extract.tmpl` | `prodId`、`planId`、计划责任、可选责任、平台原始标签 |
| `pingan` | 平安 | `PinganExtractor` | `pingan_extract.tmpl` | 产品编码、hash 路由、条款 PDF/保障表、计划版本 |
| `xiaoyusan` | 小雨伞 | `XiaoyusanExtractor` | `xiaoyusan_extract.tmpl` | 活动页产品、家庭/儿童等人群标签、保障计划、责任说明 |
| `generic` | 通用页面 | `GenericExtractor` | `generic_extract.tmpl` | 只提取有明确证据的字段，置信度更保守 |

建议文件结构：

```text
internal/skill/productdetail/platform/
  detector.go
  template.go
  raw_extract.go
  normalizer.go
  huize.go
  pingan.go
  xiaoyusan.go
  generic.go
  templates/
    huize_extract.tmpl
    pingan_extract.tmpl
    xiaoyusan_extract.tmpl
    generic_extract.tmpl
```

每个平台 adapter 只负责一件事：按照该平台模板最大程度提取该平台真实存在的字段，并保留证据。不负责编造统一字段。

模板职责边界：

1. 平台模板只输出该平台的 `PlatformRawExtract`，可以包含平台特有字段。
2. 平台模板必须要求证据片段，例如责任原文、计划原文、标签原文。
3. 平台模板不能直接输出最终 RAG chunk。
4. 统一字段由 `CanonicalNormalizer` 处理，例如 `product_type`、`standard_tags`、`canonical_duty_name`。
5. 平台模板允许字段缺失，缺失字段进入 canonical 时写 `unknown`。

示例：小雨伞解析模板应该重点要求：

```text
platform 固定为 xiaoyusan
提取页面中的产品名、计划名、适用人群、险种、平台原始标签、保障责任、责任证据片段。
如果页面出现“家庭”“亲子”“儿童”“高端医疗”等描述，放入 raw_tags，并给出 evidence。
不要把没有证据的标签写入 raw_tags。
```

### 3. 字段缺失策略

平台页面没有展示的字段不能硬补：

| 场景 | 处理方式 |
| --- | --- |
| 没有明确保额 | `coverage_text=unknown`，chunk 中写“页面未明确展示保额” |
| 没有明确是否可选 | `option_type=unknown` |
| 多计划共享同一责任名 | 按 `plan_id + duty_id` 拆分 |
| 责任名称和条款名称不一致 | `raw_name` 保留原文，`canonical_name` 做标准化 |
| 页面只有营销摘要 | 降低 `confidence`，不作为精确条款依据 |

### 4. 产品标签标准化策略

每个产品必须打三类标签：平台、险种、产品特征标签。

示例：

```text
platform: 小雨伞
type: 医疗险
tag: 高端、家庭
```

内部不要只存中文展示文本，建议同时存标准 code 和展示 label：

```json
{
  "platform": "xiaoyusan",
  "platform_label": "小雨伞",
  "product_type": "medical",
  "product_type_label": "医疗险",
  "raw_tags": ["高端医疗", "家庭保障"],
  "standard_tags": [
    {"category": "positioning", "code": "high_end", "label": "高端", "confidence": 0.88},
    {"category": "audience", "code": "family", "label": "家庭", "confidence": 0.84}
  ]
}
```

标准标签分层：

| 标签层 | 字段 | 示例 code | 示例 label |
| --- | --- | --- | --- |
| 平台 | `platform` | `xiaoyusan`、`huize`、`pingan` | 小雨伞、慧择、平安 |
| 险种 | `product_type` | `medical`、`critical_illness`、`accident`、`life`、`annuity` | 医疗险、重疾险、意外险、寿险、年金险 |
| 定位 | `positioning` | `high_end`、`budget`、`inclusive` | 高端、平价、普惠 |
| 人群 | `audience` | `family`、`child`、`senior`、`adult`、`female` | 家庭、儿童、老人、成人、女性 |
| 保障特征 | `feature` | `guaranteed_renewal`、`special_drug`、`outpatient`、`zero_deductible` | 保证续保、特药、门诊、0免赔 |
| 场景 | `scenario` | `family_plan`、`chronic_disease`、`overseas_medical` | 家庭计划、慢病友好、海外医疗 |

标签来源优先级：

1. 平台原始标签：例如平台直接返回“中高端医疗”“家庭版”。
2. 规则识别：从产品名、brief、责任项、计划名中识别关键词。
3. LLM 补充分类：只能基于页面证据推断，必须给 `confidence`，不能无证据硬打标签。

标签最终要同时进入：

1. 前端产品卡片：展示 `platform_label`、`product_type_label`、`standard_tags.label`。
2. RAG 文档 metadata：用于过滤和召回。
3. RAG chunk metadata：用于“只查小雨伞医疗险”“找高端家庭医疗险”等查询。

## 四、推荐的 RAG 数据形态

### 1. 文档层

每个产品详情页对应一条 `rag_documents`：

| 字段 | 建议值 |
| --- | --- |
| `namespace` | `product_detail` |
| `source_type` | `product_detail_ai_extract` |
| `source_url` | 规范化后的主产品 URL |
| `title` | 产品名 |
| `cleaned_text` | 由结构化责任拼接出的可读文本 |
| `metadata` | 产品名、平台、险种、标签、产品键、计划 ID、责任数量、匹配率、解析版本、完整 `raw_extract_json` 和 `canonical_json` |

注意：`source_url` 必须做平台化规范化。保留能识别产品和计划的参数，例如 `prodId`、`planId`、`DProtectPlanId`；删除 `utm_*`、`_rag_check`、临时 session 参数。

如果同一个产品有多个计划，建议不要只用 `source_url` 做知识主键，而是使用：

```text
product_key = platform + ":" + product_id
plan_key = product_key + ":" + plan_id
document_key = namespace + ":" + plan_key
```

### 2. Chunk 层

建议不用通用网页 chunker 直接切，而是基于 canonical duty 确定性生成责任级 chunks：

```text
产品：复星联合星相守2号长期医疗保险（个人版）
平台：慧择
险种：医疗险
标签：高端、家庭、保证续保
计划：108504
责任类型：必选
标准责任：住院期间外购药品及外购医疗器械费用医疗保险金
原始责任：住院期间外购药品及外购医疗器械费用医疗保险金
额度/范围：详见条款
说明：承担被保险人住院期间根据主诊医生处方购买的药品及医疗器械费用，与一般住院医疗共享免赔额
证据：页面原文片段...
来源：https://...
```

推荐 chunk 组织：

1. `chunk_index=0`：产品摘要 chunk，记录产品名、平台、必选/可选责任列表。
2. `chunk_index=1..n`：每个保障责任一个 chunk。
3. 可选增强：按“必选责任汇总”“可选责任汇总”“免赔额/续保/限制说明”额外生成聚合 chunk。

每个 chunk metadata：

```json
{
  "namespace": "product_detail",
  "source_type": "product_detail_ai_extract",
  "source_url": "产品URL",
  "product_key": "huize:104006",
  "plan_id": "108504",
  "product_name": "产品名",
  "platform": "huize",
  "platform_label": "慧择",
  "product_type": "medical",
  "product_type_label": "医疗险",
  "raw_tags": ["中高端医疗", "保证续保"],
  "standard_tag_codes": ["high_end", "family", "guaranteed_renewal"],
  "standard_tag_labels": ["高端", "家庭", "保证续保"],
  "chunk_type": "duty",
  "raw_duty_name": "平台原始责任名",
  "canonical_duty_name": "标准责任名",
  "duty_category": "inpatient_medical",
  "option_type": "required",
  "coverage_text": "详见条款",
  "confidence": 0.86
}
```

## 五、去重和避免重复 AI 解析

当前后端已有内存缓存，能避免同一进程内重复解析。但做 RAG 后还需要持久化去重。

推荐策略：

1. 请求进入 `product_detail` 时，先规范化产品 URL。
2. 通过平台 adapter 生成 `product_key` 和 `plan_key`。
3. 同步生成 `platform / product_type / standard_tags`。
4. 查询持久化详情缓存或 `rag_documents` 是否存在 `namespace=product_detail + plan_key`。
5. 如果存在且未过期：
   - 直接从 `metadata.canonical_json` 还原标准化详情。
   - 降级映射成前端需要的 `ProductDetail`。
   - 发送 `detail_items`。
   - 生成通俗解读或追问回答。
   - 不再抓网页，不再调用 LLM 抽取。
6. 如果不存在或已过期：
   - 执行平台 adapter 抓取和 AI 解析。
   - 生成 `raw_extract_json` 和 `canonical_json`。
   - 成功后先返回 `detail_items` 给前端。
   - 后台异步 embedding + upsert 入库。

现有 pgvector store 已经支持 `UNIQUE(namespace, source_url)`，短期可以把 `source_url` 填成规范化后的 `plan_key` 兼容现有表结构；长期建议增加独立 `source_key` 字段，避免 URL 和知识主键混用。

## 六、链路接入方式

### 1. 入库链路

新增一条面向平台异构数据的结构化入库链路：

```text
Product Page
  -> PlatformRawExtract
  -> CanonicalProductDetail
  -> ProductDetailToRAGDocument
  -> CanonicalDutyToChunks
  -> EmbedTexts
  -> UpsertDocumentWithChunks
```

建议接口：

```go
type PlatformExtractor interface {
    Extract(ctx context.Context, input ExtractInput) (PlatformRawExtract, error)
}

type DetailNormalizer interface {
    Normalize(raw PlatformRawExtract) (CanonicalProductDetail, error)
}

type ProductDetailIngestor interface {
    IngestCanonicalDetail(ctx context.Context, detail CanonicalProductDetail) (int64, error)
}
```

`productdetail.Service.run` 在解析成功后触发：

```text
emit detail_items
cache.Set
async ingest canonical_detail
emit answer
```

入库必须异步执行，不能阻塞 SSE。否则用户点击 AI 解析会被 embedding 和数据库写入拖慢。

### 2. 多向量命中与源数据回溯流程

向量命中只能说明某个 chunk 语义相关，不能只把 embedding 命中结果直接返回。必须通过 `document_id` 和业务 key 回溯源数据。

数据关联关系：

```text
rag_chunks.id
  -> 单条向量 chunk

rag_chunks.document_id
  -> rag_documents.id
  -> 文档级源数据：title、source_url、cleaned_text、document metadata

rag_chunks.metadata.product_key / plan_key / duty_id
  -> 业务级源数据：产品、计划、责任
  -> document metadata.canonical_json / raw_extract_json
```

检索流程：

```text
用户问题
  -> query embedding
  -> pgvector Top-K 查询 rag_chunks
  -> JOIN rag_documents 回源文档
  -> 按 plan_key / product_key / document_id 分组
  -> 聚合同一产品下的多个命中 chunk
  -> 从 document metadata 还原 canonical_json / raw_extract_json
  -> 返回 source + matches + canonical + raw_extract
  -> Agent/Answer 基于这些源数据生成回答
```

核心 SQL 形态：

```sql
SELECT
  c.id AS chunk_id,
  c.document_id,
  c.chunk_index,
  c.content,
  c.metadata AS chunk_metadata,
  d.title,
  d.source_url,
  d.cleaned_text,
  d.metadata AS document_metadata,
  1 - (c.embedding <=> $1::vector) AS score
FROM rag_chunks c
JOIN rag_documents d ON d.id = c.document_id
WHERE d.namespace = $2
ORDER BY c.embedding <=> $1::vector
LIMIT $3;
```

如果需要按平台、险种、标签过滤，可增加 metadata 条件：

```sql
AND c.metadata->>'platform' = 'xiaoyusan'
AND c.metadata->>'product_type' = 'medical'
AND c.metadata->'standard_tag_codes' ? 'high_end'
```

后端返回结构建议：

```json
{
  "query": "适合家庭的高端医疗险",
  "items": [
    {
      "source": {
        "document_id": 12,
        "product_key": "xiaoyusan:product_001",
        "plan_key": "xiaoyusan:product_001:family_plan",
        "platform": "xiaoyusan",
        "platform_label": "小雨伞",
        "product_type": "medical",
        "product_type_label": "医疗险",
        "standard_tag_labels": ["高端", "家庭"],
        "title": "产品名",
        "source_url": "https://..."
      },
      "matches": [
        {
          "chunk_id": 101,
          "chunk_index": 3,
          "score": 0.86,
          "content": "命中的责任 chunk 原文",
          "duty_id": "duty_xxx",
          "canonical_duty_name": "外购药责任"
        }
      ],
      "canonical": {},
      "raw_extract": {}
    }
  ]
}
```

聚合规则：

1. 先按 `plan_key` 分组；没有 `plan_key` 时退回 `product_key`；再没有时退回 `document_id`。
2. 同一组内保留多条命中 chunk，按 score 从高到低排序。
3. 每组计算 `best_score` 和 `matched_duty_count`。
4. 返回给模型的上下文只放命中的 chunk 和必要 metadata，避免把完整 `raw_html` 塞进 prompt。
5. 返回给前端或调试接口时可以带完整 `canonical_json`；`raw_extract_json` 默认只在调试或证据展开时返回。

### 3. 检索链路

当前 `knowledge_search` 仍然走 fallback 知识库，不会查 pgvector。需要补一个 retriever：

```text
用户问题
  -> query embedding
  -> pgvector similarity search
  -> metadata filter
  -> SearchResultItem
  -> Answer/AgentGraph
```

建议新增：

- `internal/rag/retriever/retriever.go`
- `internal/rag/store.SearchChunks`
- `internal/tool/search` 注入 `RAGKnowledgeSearcher`

检索策略：

1. 产品追问：按 `product_key` 或 `plan_key` 过滤，只查当前产品/计划。
2. 通用保险问题：查 `namespace=product_detail`，再混合 fallback 知识库。
3. 产品对比：分别过滤多个 `plan_key`，把命中的责任 chunk 交给回答模型对比。

### 4. Agent 使用方式

Agent 不需要新增复杂动作，优先复用现有动作：

- `product_detail`：负责首次解析产品详情，并触发异步入库。
- `knowledge_search`：负责从 RAG 检索已入库的产品责任、条款说明、通用知识。
- `final_answer`：基于检索上下文生成回答。

后续如要更细，可以新增内部 tool，但不一定暴露给 Planner：

- `product_detail_cache_lookup`
- `product_detail_rag_ingest`
- `product_detail_rag_search`

## 七、质量门槛

只有满足以下条件才允许入库：

1. `canonical.duties` 非空。
2. `product_key` 非空。
3. `product_name` 非空。
4. `platform` 和 `product_type` 必须可识别；无法识别时分别写 `unknown_platform`、`unknown_type`，不能留空。
5. `standard_tags` 可以为空，但已有标签必须带 `category/code/label/source/confidence`。
6. 至少 70% 的责任有页面证据片段。
7. 平台 adapter 能识别来源，或者 generic extractor 给出足够高置信度。
8. `match_rate` 达到阈值，例如 `>= 0.6`。
9. 不把用户个人问题、聊天历史、匿名 ID 写进 RAG chunk。

回答时要保留风险提示：

- `coverage_text=详见条款` 或 `unknown` 只能作为责任存在性的提示，不能当成精确额度。
- 精确赔付比例、免赔额、等待期、除外责任必须提示用户以条款和投保页面为准。

## 八、实施任务拆分

### P0：修复结构化结果可复用

已完成：

1. `product_detail` 缓存命中时继续发送 `detail_items`。
2. 单测覆盖“缓存命中不 fetch，但会返回结构化详情”。

### P1：平台异构建模

1. 新增 `PlatformRawExtract`。
2. 新增 `CanonicalProductDetail`。
3. 新增 `CanonicalDuty`，区分 `raw_name` 和 `canonical_name`。
4. 新增 `ProductClassification`，包含 `platform / product_type / raw_tags / standard_tags`。
5. 新增 `product_key / plan_key / duty_id`。
6. 单测覆盖慧择、平安、小雨伞、generic 四类页面样例。

### P2：平台 adapter

1. 新增 `PlatformExtractor` 接口。
2. 新增 `PlatformTemplateResolver`，根据 `platform` 加载对应解析模板。
3. 实现 `HuizeExtractor + huize_extract.tmpl`。
4. 实现 `PinganExtractor + pingan_extract.tmpl`。
5. 实现 `XiaoyusanExtractor + xiaoyusan_extract.tmpl`。
6. 保留 `GenericExtractor + generic_extract.tmpl` 兜底。
7. 单测验证不同平台不会误用其他平台模板。

### P3：结构化入库

1. 新增 `CanonicalDutyToChunks`。
2. 新增 `ProductDetailIngestor`。
3. 文档 metadata 写入完整 `raw_extract_json`、`canonical_json` 和标准标签。
4. chunk metadata 写入 `platform / product_type / standard_tag_codes / standard_tag_labels`。
5. 短期复用 `source_url=plan_key` 做 upsert，长期增加 `source_key`。

### P4：异步接入 AI 解析链路

1. 增加配置：`PRODUCT_DETAIL_RAG_ENABLED`。
2. 增加配置：`PRODUCT_DETAIL_RAG_NAMESPACE=product_detail`。
3. 解析成功后后台 upsert。
4. 入库失败只记录日志，不影响前端 SSE。

### P5：向量检索与源数据回溯接入

1. 扩展 `internal/rag/store.Store`：
   - 新增 `SearchChunks(ctx, query SearchChunksInput) ([]ChunkHit, error)`。
   - `ChunkHit` 必须包含 `chunk_id / document_id / chunk_index / content / score / chunk_metadata / document_metadata`。

2. 实现 pgvector Top-K 查询：
   - 使用 query embedding 与 `rag_chunks.embedding` 做相似度排序。
   - `JOIN rag_documents` 一次性带回文档源数据。
   - 支持 `namespace / platform / product_type / standard_tag_codes / product_key / plan_key` 过滤。

3. 增加源数据聚合器：
   - 新增 `internal/rag/retriever/aggregate.go`。
   - 按 `plan_key -> product_key -> document_id` 分组。
   - 同组内聚合多条命中 chunk。
   - 计算 `best_score / matched_duty_count / matched_chunk_count`。

4. 增加源数据还原：
   - 从 `document_metadata.canonical_json` 还原标准化产品详情。
   - 从 `document_metadata.raw_extract_json` 保留平台原始抽取结果。
   - 默认回答链路只使用 `canonical_json + matches`，调试接口可返回 `raw_extract_json`。

5. 新增 `RAGKnowledgeSearcher`：
   - 负责 query embedding。
   - 调用 `Store.SearchChunks`。
   - 调用聚合器生成可给 Agent 使用的 source items。
   - 返回 `SearchResultItem` 时把 `metadata` 带上。

6. 接入 `internal/tool/search`：
   - `knowledge_search` 优先查 RAG。
   - RAG 无结果或失败时 fallback 到当前 fallback 知识库。
   - `sources` 事件返回产品名、平台、险种、标签、URL、命中责任。

7. 增加调试/验证能力：
   - 提供内部 debug 方法或 CLI，输入 query 后打印命中的 chunk、score、source、canonical 摘要。
   - 用于验证“命中多条向量后能回溯到同一产品源数据”。

8. 单测覆盖：
   - 多 chunk 命中同一 `document_id` 时正确聚合。
   - 多产品同时命中时按 `plan_key` 分组。
   - metadata filter 能筛出 `platform=小雨伞`、`product_type=医疗险`、`tag=高端`。
   - `canonical_json` 缺失时不 panic，返回降级 source。
   - RAG 失败时 `knowledge_search` 能 fallback。

### P6：持久化去重和回填

1. 增加按 `namespace + plan_key` 查询文档的方法。
2. 从 `metadata.canonical_json` 还原标准化详情，避免重复 AI 解析。
3. 提供批量回填命令，把已知产品 URL 离线解析并入库。

### P7：评估与监控

1. 建立测试问题集：外购药、特药、重疾关爱金、免赔额、可选责任。
2. 建立标签评估集：小雨伞医疗险、高端医疗险、家庭医疗险、儿童医疗险、老人医疗险。
3. 分平台统计抽取成功率、证据覆盖率、字段缺失率、标签准确率。
4. 统计命中率、Top-K 相关性、回答引用完整度。
5. 记录解析耗时、入库耗时、embedding 失败率、RAG 命中率。

## 九、最终推荐

建议采用“平台 adapter + 标准化产品详情 RAG”为主，不建议只做网页原文 RAG，也不建议直接把任意平台的 AI JSON 作为最终知识。

最小可行版本：

1. 先做 `DetectPlatform`，确保每个 URL 先落到确定的平台枚举。
2. 先对慧择做 `HuizeExtractor + huize_extract.tmpl + CanonicalNormalizer`。
3. 再按同样模式补 `PinganExtractor + pingan_extract.tmpl`、`XiaoyusanExtractor + xiaoyusan_extract.tmpl`。
4. 同步生成 `platform / product_type / standard_tags`。
5. AI 解析成功后生成标准责任级 chunks。
6. 用 `product_detail` namespace upsert 到 pgvector。
7. `knowledge_search` 增加 pgvector 检索。
8. 缓存或 RAG 文档存在时直接复用 `canonical_json`，不重复 AI 解析。

这个策略允许不同平台使用不同解析模板并保留不同原始结构，但对外回答和 RAG 检索始终使用统一的标准责任知识。
