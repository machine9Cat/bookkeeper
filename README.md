# 💰 记账小助手

单位采购支出记账系统，轻量级 Web 应用，支持多用户、审核流程、统计报表、本地/云备份。

## ✨ 功能

| 模块 | 功能 |
|------|------|
| 📊 **概览** | 月度统计卡片、分类饼图、月度趋势、排行分析 |
| ✏️ **记账** | 支出录入表单，物品/规格/单位/渠道/经手人等字典自动补全 |
| 📋 **明细** | 筛选排序表格、行内编辑、快速新增、批量审核/删除、Excel 导入 |
| 📈 **统计** | 月度分类汇总、按付款方式/经手人/渠道统计、Excel/PDF 导出 |
| ⚙️ **管理** | 用户审核/禁用/重置密码、字典管理（大类/付款方式/渠道/经手人/物品/规格/单位） |
| 💾 **备份** | 本地数据库下载/上传恢复、历史 .bak 管理、30 分钟自动备份 |
| ☁️ **云备份** | WebDAV 协议（坚果云/NextCloud），gzip 压缩上传 |

## 🚀 快速启动

```bash
./start.sh
```

启动后访问 **http://localhost:8000**

首次注册的用户自动成为管理员。其余用户需管理员审核通过后方可登录。

## 📦 一键部署（开机自启）

```bash
bash deploy/install.sh
```

安装 systemd 用户服务，开机自动启动。更多详见 [部署文档](docs/deploy.md)。

## 🗂️ 项目结构

```
bookkeeper/
├── backend/
│   ├── main.py           # FastAPI 主应用（47 个 API 端点）
│   ├── database.py       # SQLite 数据库初始化与表结构
│   ├── auth.py           # JWT 认证（SHA-256 密码哈希）
│   ├── backup.py         # WebDAV 备份（gzip 压缩）
│   └── reports.py        # Excel/PDF 报表生成
├── frontend/
│   └── index.html        # 单页前端（Alpine.js + Tailwind CSS + Chart.js）
├── data/                 # 数据库与导出文件
│   ├── bookkeeper.db
│   ├── backup_log.txt
│   └── exports/
├── deploy/
│   ├── install.sh        # 一键安装部署脚本
│   └── bookkeeper.service # systemd 用户服务单元
├── docs/                 # 文档
│   ├── user-guide.md     # 用户指南
│   ├── admin-guide.md    # 管理员指南
│   └── deploy.md         # 部署指南
├── requirements.txt      # Python 依赖
├── pyproject.toml        # 项目元数据
└── start.sh              # 启动脚本
```

## 🔧 技术栈

- **后端**: Python 3.12+ / FastAPI / aiosqlite / JWT
- **前端**: Alpine.js 3.x / Tailwind CSS / Chart.js 4
- **导出**: openpyxl (Excel) / WeasyPrint (PDF)
- **备份**: aiohttp (WebDAV) / gzip 压缩
- **部署**: systemd user service

## 📖 详细文档

- [用户指南](docs/user-guide.md) — 记账、明细查询、统计报表操作说明
- [管理员指南](docs/admin-guide.md) — 用户管理、审核流程、字典管理
- [部署指南](docs/deploy.md) — 安装、开机自启、局域网访问、配置修改

## 📝 API

启动后访问 http://localhost:8000/docs 查看 Swagger 交互文档。

## 🛡️ 安全

- 密码 SHA-256 加盐哈希存储
- JWT Token 30 天有效期
- 数据隔离（用户只能访问自己的记录）
- 已审核记录不可修改/删除
- 建议内网使用或配置 HTTPS 反向代理

## 📄 许可证

MIT License
