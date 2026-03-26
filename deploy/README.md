# Docker 部署说明（单一配置）

本目录采用“单一配置维护”方式：只维护一个 `docker-compose.yml` 和一个 `.env` 模板文件。

## 目录结构

1. `docker/frontend/Dockerfile`
2. `docker/backend/Dockerfile`
3. `compose/docker-compose.yml`
4. `env/.env.example`

## 使用前需要确认

1. 前端代码目录默认为 `apps/frontend`
2. 后端代码目录默认为 `apps/backend`
3. 后端启动入口默认为 `app.main:app`
4. 后端健康检查接口默认为 `/healthz`

如果你的实际目录或入口不同，请同步修改 `docker-compose.yml` 中的 `build.context`、`dockerfile` 以及健康检查配置。

## 启动命令

```bash
docker compose \
  -f deploy/compose/docker-compose.yml \
  --env-file deploy/env/.env.example \
  up -d --build
```

## 停止命令

```bash
docker compose -f deploy/compose/docker-compose.yml down
```

## 发布流程建议

1. 在 CI 中先执行测试。
2. 构建镜像并使用不可变标签（如 `vX.Y.Z` 和 `gitsha`）。
3. 将镜像推送到镜像仓库。
4. 在 `docker-compose.yml` 中固定镜像标签后部署。
5. 发布后检查健康状态与核心指标。
6. 如有问题，回滚到上一版本镜像标签。
