#!/bin/bash
# ======================================================================
# SmartInsure Agent 一键部署脚本
#
# 使用说明:
#   1. 首次部署（构建镜像 + 启动所有服务）:
#      ./deploy.sh start
#
#   2. 开发模式（代码挂载 + 热重载，不构建镜像）:
#      ./deploy.sh dev
#
#   3. 仅重启（代码修改后）:
#      ./deploy.sh restart
#
#   4. 停止所有服务:
#      ./deploy.sh stop
#
#   5. 查看日志:
#      ./deploy.sh logs [backend|frontend]
#
#   6. 查看服务状态:
#      ./deploy.sh status
#
#   7. 健康检查:
#      ./deploy.sh check
#
# 前置要求:
#   - Docker >= 20.0 + Docker Compose >= 2.0
#   - deploy/env/.env 文件已配置（首次运行会自动从 .env.example 复制）
#
# 环境变量配置（编辑 deploy/env/.env）:
#   必填: MINIMAX_API_KEY      — MiniMax API Key（https://platform.minimaxi.com）
#   可选: MINIMAX_API_BASE     — 默认 https://api.minimaxi.com/v1
#   可选: LLM_PROVIDER         — 切换模型厂商（minimax/openai/deepseek/qwen）
# ======================================================================

set -e

# 项目根目录（脚本所在目录）
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="${PROJECT_DIR}/deploy/compose"
ENV_DIR="${PROJECT_DIR}/deploy/env"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
COMPOSE_DEV="${COMPOSE_DIR}/docker-compose.dev.yml"
ENV_FILE="${ENV_DIR}/.env"
ENV_EXAMPLE="${ENV_DIR}/.env.example"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

# ======================================================================
# 前置检查
# ======================================================================
check_prerequisites() {
    log_step "检查环境..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose v2"
        exit 1
    fi

    log_info "Docker $(docker --version | awk '{print $3}')"
    log_info "$(docker compose version)"
}

# ======================================================================
# 环境变量初始化
# ======================================================================
init_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env 文件不存在，从模板创建..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        log_warn "请编辑 ${ENV_FILE} 填入真实的 API Key"
        log_warn "  必填: MINIMAX_API_KEY"
        echo ""
        read -p "是否现在编辑 .env 文件？(y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-vi} "$ENV_FILE"
        fi
    fi

    # 检查关键配置
    if grep -q "MINIMAX_API_KEY=replace_me" "$ENV_FILE" 2>/dev/null; then
        log_warn "MINIMAX_API_KEY 尚未配置，LLM 功能将不可用"
        log_warn "请编辑 ${ENV_FILE} 填入真实的 API Key"
    fi
}

# ======================================================================
# 生产模式：构建镜像 + 启动
# ======================================================================
cmd_start() {
    log_step "=== 生产模式部署 ==="
    check_prerequisites
    init_env

    log_step "1/4 停止旧服务..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down 2>/dev/null || true

    log_step "2/4 构建镜像（后端）..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build backend

    log_step "3/4 启动基础设施（Redis + PostgreSQL）..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d redis postgres
    sleep 3

    log_step "4/4 启动后端..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend
    sleep 5

    # 启动前端（宿主机模式，避免 Docker 内 npm ci 网络问题）
    start_frontend_host

    log_info "=== 部署完成 ==="
    cmd_check
}

# ======================================================================
# 开发模式：代码挂载 + 热重载
# ======================================================================
cmd_dev() {
    log_step "=== 开发模式部署 ==="
    check_prerequisites
    init_env

    log_step "1/3 停止旧服务..."
    docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_DEV" --env-file "$ENV_FILE" down 2>/dev/null || true

    log_step "2/3 启动后端 + 基础设施（代码挂载 + 热重载）..."
    docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_DEV" --env-file "$ENV_FILE" up -d backend redis postgres
    sleep 5

    log_step "3/3 启动前端..."
    start_frontend_host

    log_info "=== 开发模式启动完成 ==="
    cmd_check
}

# ======================================================================
# 前端宿主机启动（绕过 Docker 内 npm 网络问题）
# ======================================================================
start_frontend_host() {
    log_step "启动前端（宿主机模式）..."

    FRONTEND_DIR="${PROJECT_DIR}/apps/frontend"

    # 检查 node_modules
    if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
        log_info "安装前端依赖..."
        cd "$FRONTEND_DIR" && npm install --silent 2>&1 | tail -3
        cd "$PROJECT_DIR"
    fi

    # 杀掉已有的前端进程
    lsof -ti:3001 2>/dev/null | xargs kill -9 2>/dev/null || true

    # 后台启动 Next.js dev server
    cd "$FRONTEND_DIR"
    API_UPSTREAM=http://localhost:8000 nohup npx next dev -H 0.0.0.0 -p 3001 > /tmp/smartinsure-frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd "$PROJECT_DIR"

    # 等待就绪
    log_info "等待前端就绪 (PID: $FRONTEND_PID)..."
    for i in $(seq 1 15); do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null | grep -q "200"; then
            log_info "前端已就绪"
            return 0
        fi
        sleep 2
    done
    log_warn "前端启动超时，请检查 /tmp/smartinsure-frontend.log"
}

# ======================================================================
# 重启（不重建镜像）
# ======================================================================
cmd_restart() {
    log_step "重启服务..."

    # 判断是 dev 模式还是 prod 模式
    if docker inspect compose-backend-1 2>/dev/null | grep -q '"Source.*apps/backend"'; then
        log_info "检测到开发模式，使用 dev compose 重启..."
        docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_DEV" --env-file "$ENV_FILE" restart backend
    else
        log_info "生产模式重启..."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart backend
    fi

    # 重启前端
    lsof -ti:3001 2>/dev/null | xargs kill -9 2>/dev/null || true
    start_frontend_host

    log_info "重启完成"
    cmd_check
}

# ======================================================================
# 停止
# ======================================================================
cmd_stop() {
    log_step "停止所有服务..."

    # 停止 Docker 服务
    docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_DEV" --env-file "$ENV_FILE" down 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down 2>/dev/null || true

    # 停止宿主机前端
    lsof -ti:3001 2>/dev/null | xargs kill -9 2>/dev/null || true

    log_info "所有服务已停止"
}

# ======================================================================
# 查看日志
# ======================================================================
cmd_logs() {
    local service="${1:-backend}"
    if [ "$service" = "frontend" ]; then
        log_info "前端日志 (/tmp/smartinsure-frontend.log):"
        tail -50 /tmp/smartinsure-frontend.log 2>/dev/null || log_warn "前端日志不存在"
    else
        docker logs "compose-${service}-1" --tail 50 -f 2>/dev/null || log_error "容器 compose-${service}-1 不存在"
    fi
}

# ======================================================================
# 服务状态
# ======================================================================
cmd_status() {
    log_step "服务状态:"
    echo ""

    # Docker 容器
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=compose-" 2>/dev/null || true
    echo ""

    # 前端进程
    if lsof -ti:3001 &>/dev/null; then
        log_info "前端: 运行中 (端口 3001)"
    else
        log_warn "前端: 未运行"
    fi
}

# ======================================================================
# 健康检查
# ======================================================================
cmd_check() {
    echo ""
    log_step "=== 健康检查 ==="

    # 后端 healthz
    local backend_status
    backend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/healthz 2>/dev/null || echo "000")
    if [ "$backend_status" = "200" ]; then
        log_info "后端 API:     http://localhost:8000/api/healthz  ✓ (200)"
    else
        log_error "后端 API:     http://localhost:8000/api/healthz  ✗ ($backend_status)"
    fi

    # 后端 suggestions
    local suggest_status
    suggest_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/suggestions 2>/dev/null || echo "000")
    if [ "$suggest_status" = "200" ]; then
        log_info "推荐问题:     http://localhost:8000/api/suggestions  ✓ (200)"
    else
        log_error "推荐问题:     http://localhost:8000/api/suggestions  ✗ ($suggest_status)"
    fi

    # 后端 providers
    local provider_status
    provider_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/providers 2>/dev/null || echo "000")
    if [ "$provider_status" = "200" ]; then
        local available
        available=$(curl -s http://localhost:8000/api/providers 2>/dev/null | python3 -c "import sys,json; print(','.join(json.load(sys.stdin).get('available',[])))" 2>/dev/null || echo "未知")
        log_info "LLM Providers: http://localhost:8000/api/providers  ✓ (可用: $available)"
    else
        log_error "LLM Providers: http://localhost:8000/api/providers  ✗ ($provider_status)"
    fi

    # 前端
    local frontend_status
    frontend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null || echo "000")
    if [ "$frontend_status" = "200" ]; then
        log_info "前端页面:     http://localhost:3001  ✓ (200)"
    else
        log_error "前端页面:     http://localhost:3001  ✗ ($frontend_status)"
    fi

    # 前端代理后端
    local proxy_status
    proxy_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/api/healthz 2>/dev/null || echo "000")
    if [ "$proxy_status" = "200" ]; then
        log_info "前端→后端代理: http://localhost:3001/api/healthz  ✓ (200)"
    else
        log_error "前端→后端代理: http://localhost:3001/api/healthz  ✗ ($proxy_status)"
    fi

    echo ""
    log_info "前端访问地址: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):3001"
    log_info "后端 API 地址: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8000"
}

# ======================================================================
# 主入口
# ======================================================================
case "${1:-help}" in
    start)   cmd_start ;;
    dev)     cmd_dev ;;
    restart) cmd_restart ;;
    stop)    cmd_stop ;;
    logs)    cmd_logs "$2" ;;
    status)  cmd_status ;;
    check)   cmd_check ;;
    *)
        echo "SmartInsure Agent 部署脚本"
        echo ""
        echo "用法: $0 <命令>"
        echo ""
        echo "命令:"
        echo "  start     生产模式部署（构建镜像 + 启动所有服务）"
        echo "  dev       开发模式部署（代码挂载 + 热重载，不构建镜像）"
        echo "  restart   重启服务（不重建镜像）"
        echo "  stop      停止所有服务"
        echo "  logs      查看日志 (logs backend | logs frontend)"
        echo "  status    查看服务状态"
        echo "  check     健康检查"
        echo ""
        echo "首次部署步骤:"
        echo "  1. cp deploy/env/.env.example deploy/env/.env"
        echo "  2. 编辑 deploy/env/.env，填入 MINIMAX_API_KEY"
        echo "  3. ./deploy.sh dev"
        ;;
esac
