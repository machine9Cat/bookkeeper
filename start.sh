#!/bin/bash
# 记账小助手启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}💰 记账小助手${NC}"
echo "========================"

# 检查 Python
echo -ne "${CYAN}[1/4]${NC} 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo -e "\r${CYAN}[1/4]${NC} ❌ 需要 Python 3.8+"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo -e "\r${CYAN}[1/4]${NC} ✅ $PY_VER"

# 创建虚拟环境
echo -ne "${CYAN}[2/4]${NC} 检查虚拟环境..."
if [ ! -d "venv" ]; then
    echo -e "\r${CYAN}[2/4]${NC} 📦 创建虚拟环境..."
    if command -v uv &> /dev/null; then
        uv venv venv --python 3.12 2>&1
    else
        python3 -m venv venv 2>&1
    fi
    echo -e "\r${CYAN}[2/4]${NC} ✅ 虚拟环境创建完成"
else
    echo -e "\r${CYAN}[2/4]${NC} ✅ 虚拟环境已存在"
fi

# 安装依赖
echo -ne "${CYAN}[3/4]${NC} 安装依赖..."
if command -v uv &> /dev/null; then
    uv pip install --python venv/bin/python -r requirements.txt 2>&1
else
    venv/bin/pip install -r requirements.txt 2>&1
fi
echo -e "\r${CYAN}[3/4]${NC} ✅ 依赖安装完成"

# 创建必要目录
echo -ne "${CYAN}[4/4]${NC} 初始化目录..."
mkdir -p data/exports backups
echo -e "\r${CYAN}[4/4]${NC} ✅ 目录准备完成"

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
