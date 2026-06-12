# 🚀 部署指南

## 目录

- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [一键部署（开机自启）](#一键部署开机自启)
- [局域网访问](#局域网访问)
- [配置修改](#配置修改)
- [服务管理](#服务管理)
- [更新升级](#更新升级)

---

## 环境要求

- Python 3.12+
- Linux 系统（推荐 Ubuntu 22.04+）
- 可选：`uv`（快速包管理器）

## 快速启动

```bash
# 克隆项目后进入目录
cd bookkeeper

# 直接启动
./start.sh
```

启动后访问 http://localhost:8000

首次注册的用户自动成为**管理员**。

## 一键部署（开机自启）

使用部署脚本自动完成环境初始化、服务安装和自启配置：

```bash
bash deploy/install.sh
```

该脚本会：
1. 创建 Python 虚拟环境并安装依赖
2. 初始化数据目录
3. 安装 systemd **用户级** 服务
4. 启用开机自启并立即启动服务
5. 显示本地和局域网访问地址

## 局域网访问

服务默认监听 `0.0.0.0:8000`（所有网络接口），同局域网设备可直接访问。

**查看局域网地址：**
```bash
# Linux
hostname -I | awk '{print $1}'
```

启动 `start.sh` 或 `deploy/install.sh` 时会自动显示局域网访问 URL。

**访问格式：** `http://192.168.x.x:8000`

### WSL2 特殊配置

如果运行在 **WSL2** 环境下，外部设备无法直接通过 WSL 的 IP 访问（WSL2 使用 NAT 网络）。需要设置 Windows 端口转发：

**方式一：一键设置（推荐）**

在 Windows 文件管理器中双击 `deploy\wsl-port-forward.bat`，或直接在 PowerShell（管理员）中执行：

```powershell
# 从 WSL 内复制到 Windows 临时目录后运行
cd \\wsl.localhost\Ubuntu\home\administrator\jmrspace\bookkeeper\deploy
.\wsl-port-forward.bat
```

脚本会：
1. 添加 Windows 防火墙入站规则（允许 TCP 8000 端口）
2. 设置 `netsh interface portproxy` 将 Windows 的 8000 端口转发到 WSL2
3. 显示当前转发规则

**方式二：PowerShell 脚本**

```powershell
powershell -ExecutionPolicy Bypass -File wsl-port-forward.ps1
```

**方式二：Windows 开机自启**

创建一个 Windows 任务计划程序任务，开机时自动执行上述脚本。

**方式三：手动设置**

```powershell
# 以管理员身份运行
netsh interface portproxy add v4tov4 listenport=8000 connectaddress=(wsl hostname -I).Trim().Split()[0] connectport=8000
```

> **注意**：WSL2 重启后 IP 地址可能变化，需要重新设置端口转发。建议设置 WSL2 为固定 IP 或每次启动后运行转发脚本。

## 配置修改

### 修改端口

编辑 `backend/main.py` 最后一行：

```python
uvicorn.run(app, host="0.0.0.0", port=8000)  # 修改为需要的端口
```

修改后需重启服务。

### 数据库位置

默认路径：`data/bookkeeper.db`。

如需修改，编辑 `backend/database.py` 中的 `DB_PATH` 变量，并重新启动。

### 反向代理（Nginx）

推荐在生产环境使用 Nginx 反代 + HTTPS：

```nginx
server {
    listen 443 ssl;
    server_name bookkeeper.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 服务管理

使用 systemd 用户服务管理应用：

```bash
# 查看状态
systemctl --user status bookkeeper.service

# 启动
systemctl --user start bookkeeper.service

# 停止
systemctl --user stop bookkeeper.service

# 重启
systemctl --user restart bookkeeper.service

# 查看实时日志
journalctl --user -u bookkeeper.service -f

# 查看全部日志
journalctl --user -u bookkeeper.service --since "1 hour ago"
```

> 如果使用 systemd 用户服务，确保已执行 `sudo loginctl enable-linger $(whoami)`，否则用户登出后服务会停止。`deploy/install.sh` 会自动执行此操作。

## 更新升级

```bash
# 进入项目目录
cd /home/administrator/jmrspace/bookkeeper

# 拉取最新代码
git pull

# 更新依赖
./venv/bin/pip install -r requirements.txt --quiet

# 重启服务
systemctl --user restart bookkeeper.service
```

## 常见问题

### 端口被占用

```bash
# 查看占用 8000 端口的进程
ss -tlnp | grep 8000

# 或使用 systemd 重启（自动关闭旧进程）
systemctl --user restart bookkeeper.service
```

### 数据库损坏

使用备份恢复：
1. 在备份页面上传最新的 `.bak` 文件
2. 或直接替换 `data/bookkeeper.db` 为备份文件
3. 重启服务

### 重置管理员密码

直接操作数据库：
```bash
# 连接数据库
sqlite3 data/bookkeeper.db

# 更新管理员密码（新密码为 admin123）
UPDATE users SET password_hash='240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', raw_password='admin123' WHERE username='admin';
.quit
```

或注册新用户（第一个注册的自动成为管理员）。
