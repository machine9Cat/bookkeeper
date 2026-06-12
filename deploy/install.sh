#!/bin/bash
# 记账小助手 - 一键安装 & 自启动配置脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}💰 记账小助手 - 安装部署${NC}"
echo "========================"

# 1. 创建虚拟环境 & 安装依赖
echo -e "${YELLOW}📦 安装依赖...${NC}"
if [ ! -d "venv" ]; then
    if command -v uv &> /dev/null; then
        uv venv venv --python 3.12
    else
        python3 -m venv venv
    fi
fi
# 统一使用 venv（避免 uv 默认使用 .venv 导致的冲突）
export UV_PROJECT_ENVIRONMENT=venv
if command -v uv &> /dev/null; then
    uv pip install -q -r requirements.txt
else
    # venv 由 uv 创建时没有 pip，需要手动安装
    venv/bin/python -m ensurepip --upgrade 2>/dev/null || true
    venv/bin/pip install -q -r requirements.txt
fi

# 2. 创建必要目录
mkdir -p data exports

# 3. 初始化数据库（首次启动会自动建表）
echo -e "${YELLOW}🗄️  初始化数据库...${NC}"
venv/bin/python backend/database.py 2>/dev/null || true

# 4. 安装 systemd user 服务
echo -e "${YELLOW}⚙️  安装系统服务（开机自启）...${NC}"
mkdir -p ~/.config/systemd/user/
cp deploy/bookkeeper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable bookkeeper.service
systemctl --user restart bookkeeper.service 2>/dev/null || true

# 5. 启用 lingering（允许用户服务在无登录会话时运行）
sudo loginctl enable-linger "$(whoami)" 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ 安装完成！${NC}"
echo ""

# 6. 显示访问地址
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo -e "${CYAN}📊 本地访问:    http://localhost:8000${NC}"
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${YELLOW}⚠️  检测到 WSL 环境${NC}"
    echo -e "${YELLOW}   局域网访问需设置 Windows 端口转发:${NC}"
    echo -e "${YELLOW}   以管理员身份双击 deploy/wsl-port-forward.bat 即可${NC}"
elif [ -n "$LAN_IP" ]; then
    echo -e "${CYAN}🌐 局域网访问:  http://${LAN_IP}:8000${NC}"
fi
echo -e "${YELLOW}📌 服务已设置为开机自启${NC}"
echo -e "${YELLOW}   管理命令: systemctl --user {start|stop|restart|status} bookkeeper.service${NC}"
echo -e "${YELLOW}   查看日志: journalctl --user -u bookkeeper.service -f${NC}"
echo ""
