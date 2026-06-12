---
name: add-insurance-platform
description: 新增保险平台 API 接入技能。用户提供平台 API 信息（curl 示例或接口文档），自动生成符合架构规范的平台适配器代码、注册到平台列表、编写单元测试并自测通过。
---

# 新增保险平台 API 接入技能

## 适用场景

当需要接入一个新的保险平台产品搜索 API 时调用此技能。

## 用户输入规范

请用户按以下模板提供信息（缺失项会在流程中追问）：

```
【平台名称】必填。如：众安保险
【平台域名】必填。如：zhongan.com
【接口地址】必填。完整 URL，如：https://api.example.com/search
【请求方式】必填。GET 或 POST
【请求格式】必填。以下三选一：
  - query-string（GET 参数）
  - form-data（POST 表单）
  - json（POST JSON）
【curl 示例】强烈推荐。一个可运行的 curl 命令，包含完整 headers 和 body：
  curl -X POST 'https://api.example.com/search' \
    -H 'Content-Type: application/json' \
    -d '{"keyword":"医疗","page":1}'
【响应示例】强烈推荐。接口返回的 JSON 片段（至少包含 1 个产品），用于确认字段映射：
  {"code":0,"data":{"list":[{"title":"xxx","price":168,...}]}}
【认证方式】必填。以下之一：
  - 无需认证
  - 需要 Cookie（提供环境变量名，如 ZHONGAN_COOKIE）
  - 需要 API Key（提供环境变量名，如 ZHONGAN_API_KEY）
  - 其他（说明具体方式）
【字段映射】可选。如果响应 JSON 结构清晰，可由代码自动推断。否则请指定：
  - 产品名称字段：如 data.list[].title
  - 产品价格字段：如 data.list[].price（注明单位：元 or 分）
  - 产品链接字段：如 data.list[].url
  - 保险公司字段：如 data.list[].company（如无，将从产品名提取）
  - 产品简介字段：如 data.list[].description
  - 标签/分类字段：如 data.list[].category
【特殊说明】可选。如：
  - 价格单位是分需要除以 100
  - Referer 中文需 URL 编码
  - 需要特殊 headers
  - 分页参数名称
```

### 最小输入示例

只提供 curl + 响应即可启动（其余自动推断）：

```
平台：众安保险（zhongan.com）
认证：无需认证

curl 'https://api.zhongan.com/product/search?keyword=医疗&page=1' \
  -H 'User-Agent: Mozilla/5.0'

响应：
{"code":0,"data":[{"name":"众安百万医疗","price":"168元/年","url":"https://...","company":"众安保险"}]}
```

## 执行流程

### 阶段 1：解析输入

1. 从用户输入中提取：平台名、域名、接口 URL、请求方式、请求格式、认证方式
2. 从 curl 示例中解析：headers、body 结构、query 参数
3. 从响应示例中推断字段映射：产品名→name、价格→price、链接→url、公司→company、简介→brief、标签→tags
4. 如关键信息缺失，向用户追问（不猜测接口地址和认证方式）

### 阶段 2：生成代码

创建文件 `apps/backend/app/services/platform_apis/{platform_id}.py`，遵循以下架构规范：

```python
"""
{平台名称}保险平台 API

搜索接口：{请求方式} {接口地址}
请求格式：{请求格式描述}
响应格式：{响应结构摘要}
"""

import hashlib
import logging
from typing import Optional

import httpx

from app.schemas.chat import ProductCard
from app.services.platform_apis.base import PlatformAPI

logger = logging.getLogger(__name__)


class {ClassName}API(PlatformAPI):
    """{平台名称}保险 API"""

    name = "{平台名称}"
    domain = "{平台域名}"

    API_URL = "{接口地址}"

    async def search(self, keyword: str, page: int = 1) -> list[ProductCard]:
        headers = { ... }  # 从 curl 解析
        # body / params 构造
        # httpx.AsyncClient 发起请求
        # 解析响应 → ProductCard 列表
        ...
```

**代码规范要求**：
- 继承 `PlatformAPI` 抽象基类
- 实现 `search(keyword, page)` 方法，返回 `list[ProductCard]`
- 使用 `httpx.AsyncClient(timeout=httpx.Timeout(10.0))` 发起请求
- `ProductCard` 字段映射：
  - `id`：`"{platform_prefix}_{原始ID}"` 或 `"{platform_prefix}_{name的md5前8位}"`
  - `name`：产品名称（必填）
  - `company`：保险公司（无则从产品名正则提取或留空）
  - `price`：格式化为 `"XXX元/年起"` 或 `"XXX元/月起"`（注意单位转换）
  - `price_label`：与 price 相同，无价格时 `"查看详情"`
  - `tags`：最多 3 个标签
  - `url`：真实投保/详情页链接（必填，跳过无链接的产品）
  - `platform`：`self.name`
  - `brief`：一句话简介
- 异常处理：`resp.raise_for_status()`，外层由 `_safe_search` 捕获
- 日志：`logger.info("[{平台名}] 搜索 '%s' 返回 %d 个产品", keyword, len(products))`
- 中文注释说明关键字段映射逻辑
- 如需 Cookie/API Key，从环境变量读取：`os.environ.get("{ENV_VAR_NAME}", "")`

### 阶段 3：注册平台

修改 `apps/backend/app/services/platform_apis/__init__.py`：

1. 顶部添加 import：`from app.services.platform_apis.{platform_id} import {ClassName}API`
2. 在 `PLATFORMS` 列表中追加：`{ClassName}API()`

### 阶段 4：编写测试

创建 `apps/backend/tests/test_{platform_id}_api.py`：

```python
"""
{平台名称}平台 API 单元测试

测试内容：
1. 响应解析：模拟 API 响应 JSON → ProductCard 字段映射
2. 异常处理：网络超时 / 空响应 / 异常状态码
3. 字段边界：缺失字段、价格为空、URL 为空时的处理
"""
```

**测试用例清单**（最少 6 个）：
1. `test_parse_normal_response` — 正常响应解析为 ProductCard
2. `test_product_fields_mapping` — 各字段映射正确（name/price/url/company/tags/brief）
3. `test_price_format` — 价格格式化正确（单位转换、"元/年起" 后缀）
4. `test_skip_incomplete_products` — 缺少 name 或 url 的产品被跳过
5. `test_empty_response` — 空结果返回空列表
6. `test_id_generation` — 产品 ID 前缀正确且唯一

### 阶段 5：自测验证

1. **语法检查**：`python3 -c "import ast; ast.parse(open('{file}').read())"`
2. **单元测试**：`python3 -m pytest tests/test_{platform_id}_api.py -v`
3. **全量回归**：`python3 -m pytest tests/ -q`（确认无回归）
4. **远程验证**（如果用户要求）：
   - 同步代码到远程
   - 重启后端
   - 发一个真实搜索请求验证产品返回

### 阶段 6：更新文档

更新 `CLAUDE.md` 中的平台直连 API 表格：

```markdown
| {平台名} | `{请求方式} {接口路径}` | {认证描述} |
```

## 输出物

1. `app/services/platform_apis/{platform_id}.py` — 平台适配器代码
2. `tests/test_{platform_id}_api.py` — 单元测试（≥6 个用例）
3. `__init__.py` 更新 — import + PLATFORMS 注册
4. `CLAUDE.md` 更新 — 平台 API 表格新增一行

## 验收门禁

1. `search()` 返回 `list[ProductCard]`，字段完整
2. 单元测试 ≥ 6 个用例，全部通过
3. 全量 `pytest tests/` 无回归
4. 已在 `PLATFORMS` 列表注册
5. 如用户提供了 curl 示例，真实请求能返回产品数据
