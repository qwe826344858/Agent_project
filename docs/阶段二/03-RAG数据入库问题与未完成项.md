# 阶段二：RAG 数据入库问题与未完成项

状态：阶段二探索中  
更新时间：2026-04-14

## 一、背景

本轮尝试在现有项目中补充一条“手动触发的数据获取 -> HTML 清洗 -> 切块 -> Embedding -> 向量入库”链路，目标是为后续 RAG 检索能力做准备。

本轮已补充的代码能力主要包括：

1. 通用网页抓取服务：`apps/backend/app/services/webpage_fetcher.py`
2. 文本切块服务：`apps/backend/app/services/text_chunker.py`
3. Embedding 客户端：`apps/backend/app/services/embedding_client.py`
4. PostgreSQL/pgvector 入库服务：`apps/backend/app/services/pgvector_store.py`
5. 入库编排服务：`apps/backend/app/services/ingestion_service.py`
6. 手动触发脚本：`apps/backend/scripts/ingest_urls.py`

这些能力目前仍属于“阶段二实验能力”，**未接入当前主聊天链路**。

## 二、本轮确认过的问题

### 1. PostgreSQL 主版本与 pgvector 版本不匹配

最初尝试在现有 `PostgreSQL 16` 环境中直接补装 `pgvector`。实际验证发现：

1. Alpine 仓库中的 `postgresql-pgvector` 包依赖 `postgresql18`
2. 当前项目原始数据库服务为 `postgres:16-alpine`
3. 将 PG18 的 `vector.so` / `vector.control` 复制到 PG16 目录后，数据库报错：
   - `Server is version 16, library is version 18`

结论：

- `PG16` 不能直接加载 `PG18` 的 `pgvector`
- 如果要在 PG16 上使用 pgvector，必须拿到 **PG16 对应版本** 的扩展构建产物

### 2. 在现有容器内编译 PG16 版 pgvector 不稳定

尝试在远端现有 `compose-postgres-1` 容器内：

1. 安装编译依赖
2. 拉取 `pgvector` 源码
3. 通过当前容器内的 `pg_config` 编译 PG16 对应扩展

实际多次受外部网络影响失败，主要包括：

1. Alpine 包仓库 `502 Bad Gateway`
2. `mpc1` 等编译依赖下载不稳定
3. GitHub 拉取 `pgvector` 源码时 TLS/EOF 错误

结论：

- 在现有容器内临时补编译的方式不稳定
- 即使 demo 环境可以尝试，也不适合作为长期可重复部署方案

### 3. PG18 + pgvector 的 demo 升级路径可以跑通数据库底座

后续改为 demo 方案，直接升级数据库到 `PostgreSQL 18`，并使用以下镜像源：

- `swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/postgres:18.3-alpine3.23`

同时通过 Dockerfile 将 `postgresql-pgvector` 包中的扩展文件复制到官方 PostgreSQL 18 镜像目录。

远端验证结果：

1. 数据库已成功启动为 `PostgreSQL 18.3`
2. `CREATE EXTENSION vector;` 执行成功
3. `pgvector` 数据库侧能力已验证可用

### 4. Embedding 阶段仍未打通

在数据库升级和 `pgvector` 可用后，继续执行 `ingest_urls.py`，发现入库流程仍然没有完成。

当前剩余问题主要有两个：

#### 4.1 外部网页 HTTPS 证书问题

使用脚本抓取 `https://example.com` 时，后端容器内出现：

- `SSL: CERTIFICATE_VERIFY_FAILED`

虽然已将网页抓取器改为使用 `certifi`，但当前远端环境对外网 HTTPS 抓取仍不稳定，仍需进一步确认远端容器证书链与网络策略。

#### 4.2 Embedding 接口未稳定打通

当前 `EmbeddingClient` 默认读取到的配置为：

1. `api_base=https://api.minimaxi.com/v1`
2. `model=text-embedding-3-small`

实际运行中，在调用 embedding 接口时又出现：

- `httpx.ConnectTimeout`

这说明：

1. 当前抓取、清洗、切块、数据库建表已经能走通
2. 真正阻塞入库完成的最后一步是 **Embedding 服务调用**

目前尚未确认：

1. 当前远端网络是否能稳定访问该 embedding 接口
2. `MiniMax` OpenAI 兼容入口是否支持 `text-embedding-3-small`
3. 是否需要切到单独的 embedding provider

## 三、已完成但未接入主链路的能力

以下能力代码已存在，但当前未接入 `/api/chat` 主流程：

1. 手动 URL 入库脚本
2. 网页抓取与 HTML 清洗
3. 切块与 chunk metadata 组织
4. PostgreSQL 文档表 / chunk 表写入
5. pgvector 向量字段存储

当前项目主链路仍然是：

1. 聊天接口
2. 意图识别
3. 平台搜索 / fallback 知识库
4. LLM 生成回答
5. SSE 输出

也就是说，**阶段二的 RAG 入库能力尚未替换当前主问答流程**。

## 四、为保证当前服务可用所做的处理

为了不让阶段二探索影响当前稳定链路，本仓库已做如下处理：

1. `deploy/compose/docker-compose.yml` 中的 `postgres` 服务已回退为原始稳定配置：
   - `image: postgres:16-alpine`
2. 删除阶段二实验性数据库镜像文件：
   - `deploy/docker/postgres/Dockerfile`
3. 保留阶段二实验代码，但不自动接入当前主流程

这样处理后，仓库默认部署路径回到“本次探索前的稳定逻辑”：

1. 主聊天链路不依赖 pgvector
2. 不要求数据库升级到 PG18
3. 不要求 Embedding 服务必须可用

## 五、当前未完成功能点

### F2-RAG-01：稳定的向量数据库部署方案

未完成内容：

1. 确定正式使用 `PG16 + PG16 对应 pgvector` 还是 `PG18 + PG18 对应 pgvector`
2. 形成可重复部署的数据库镜像方案
3. 在仓库层完成对应 compose / Dockerfile 固化

### F2-RAG-02：Embedding 服务配置与连通性

未完成内容：

1. 明确使用哪个 provider 提供 embedding
2. 明确对应模型名
3. 验证远端容器的网络与 TLS 证书链
4. 保证批量 embedding 返回格式稳定

### F2-RAG-03：真实入库闭环验证

未完成内容：

1. 对真实网页抓取成功
2. 清洗后达到最小文本阈值
3. 成功生成 embedding
4. 成功写入 `rag_documents` / `rag_chunks`
5. 验证向量检索可查回

### F2-RAG-04：检索接入主问答链路

未完成内容：

1. Retriever 查询封装
2. `vector similarity` / Top-K 查询
3. 检索结果重排
4. 主聊天编排器接入 RAG 上下文
5. 回答引用与来源显示

## 六、建议的后续处理顺序

建议后续按以下顺序推进：

1. 先确定数据库版本策略  
   建议不要在 PG16 / PG18 之间反复摇摆，先固定一个主版本。

2. 再固定 embedding provider  
   先验证哪个 provider 能稳定提供 embedding，再继续打通入库。

3. 然后完成单 URL 入库闭环  
   先保证 `ingest_urls.py` 对一条测试页面能成功写库。

4. 最后再考虑接入主链路  
   在没有完成稳定写库和稳定检索前，不应接入当前 `/api/chat` 生产链路。

## 七、当前结论

当前阶段二结论如下：

1. RAG 入库实验代码已具备基础骨架
2. 当前主链路仍应保持原有搜索优先流程
3. 现阶段不应让 pgvector / embedding 依赖成为主服务启动前置条件
4. 阶段二探索应继续隔离推进，待数据库版本与 embedding 连通性稳定后再考虑合入主链路
