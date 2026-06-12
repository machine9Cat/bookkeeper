#!/bin/bash
# 记账小助手启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}💰 记账小助手${NC}"
echo "========================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.8+"
    exit 1
fi

# 创建虚拟环境（使用 uv 如果可用）
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
    if command -v uv &> /dev/null; then
        uv venv venv --python 3.12
    else
        python3 -m venv venv
    fi
fi

# 安装依赖
echo -e "${YELLOW}📦 检查依赖...${NC}"
if command -v uv &> /dev/null; then
    uv pip install --python venv/bin/python -q -r requirements.txt
else
    venv/bin/pip install -q -r requirements.txt
fi

# 创建必要目录
mkdir -p data/exports backups

# 显示访问地址
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo -e "${GREEN}🚀 服务已启动${NC}"
echo -e "${GREEN}📊 本地访问:   http://localhost:8000${NC}"
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${YELLOW}⚠️  检测到 WSL 环境${NC}"
    echo -e "${YELLOW}   局域网访问需设置 Windows 端口转发:${NC}"
    echo -e "${YELLOW}   以管理员身份双击 deploy/wsl-port-forward.bat 即可${NC}"
elif [ -n "$LAN_IP" ]; then
    echo -e "${GREEN}🌐 局域网访问: http://${LAN_IP}:8000${NC}"
fi
echo -e "${YELLOW}按 Ctrl+C 停止${NC}"
echo ""

cd backend
../venv/bin/python main.py
