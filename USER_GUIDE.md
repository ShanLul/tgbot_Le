# LeBot2 使用说明

## 简介

LeBot2 是一个 Telegram 智能算价机器人，支持群组账单管理和订单金额自动识别。

---

## 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制 .env.example 为 .env 并修改）
cp .env.example .env

# 3. 启动项目
python main.py
```

### Docker 部署

```bash
# 1. 构建并启动
docker compose up -d

# 2. 查看日志
docker compose logs -f

# 3. 停止
docker compose down
```

---

## 功能说明

### 1. 订单报单

报单时需要在消息**前加 `a` 或 `A` 前缀**，否则不会被识别。

**示例：**

```
a d程
13045201820
黑龙江省齐齐哈尔市依安县依安镇翰林新居六栋一单元

雪茄鸭嘴兽 铁观音 绿豆 备选龙井
高维 绿豆 备选蓝莓
总186
```

**支持的金额格式：**
- `总186` - 直接识别金额
- `总60*2+60+6=186` - 带算式的金额

---

## 命令列表

### 基础命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用，显示欢迎信息 |
| `/help` | 显示帮助信息 |
| `/bill` 或 `/账单` | 查看当前群组账单 |
| `/history` | 查看最近账单历史 |
| `/id` | 查看用户ID（回复他人消息可查看对方ID） |

### 管理员命令

| 命令 | 说明 |
|------|------|
| `/set_admin` | 设置管理员 |
| `/setadmin` | 同上（别名，不带下划线） |

**设置管理员用法：**
- 设置**全局管理员**（所有群组有效）：`/set_admin --global` 或 `/set_admin <用户ID> --global`
- 设置**群组管理员**（仅当前群组）：`/set_admin` 或 `/set_admin <用户ID>`

---

## 权限说明

### 超级管理员
- 在 `.env` 文件中配置 `SUPER_ADMIN_IDS`
- 可以设置全局管理员和群组管理员
- 所有群组自动拥有管理员权限

### 全局管理员
- 由超级管理员设置
- 在所有群组中都拥有管理员权限

### 群组管理员
- 由超级管理员设置
- 仅在指定群组中拥有管理员权限

---

## 管理员功能

管理员可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `+金额` | 增加账单（如：`+100`） |
| `-金额` | 减少账单（如：`-50`） |
| `清账` | 清空账单和历史数据 |

---

## 配置说明

编辑 `.env` 文件：

```ini
# Telegram Bot Token（从 @BotFather 获取）
BOT_TOKEN=你的Bot_Token

# 超级管理员ID（逗号分隔多个）
SUPER_ADMIN_IDS=123456789,987654321

# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db

# API 配置
API_HOST=0.0.0.0
API_PORT=8001

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log
```

### 获取 Telegram 用户 ID

1. 在 Telegram 中发送 `/id` 命令
2. 回复他人消息后发送 `/id` 可查看对方 ID

### 获取 Bot Token

1. 在 Telegram 中找到 @BotFather
2. 发送 `/newbot` 创建新 Bot
3. 按提示设置名称
4. 保存返回的 Token

---

## API 接口

Bot 启动后，可访问以下接口：

| 路径 | 说明 |
|------|------|
| `http://localhost:8001/` | 项目信息 |
| `http://localhost:8001/health` | 健康检查 |
| `http://localhost:8001/bot/info` | Bot 配置信息 |

---

## 部署到服务器

### 阿里云 ECS 部署

```bash
# 1. 连接服务器
ssh root@你的服务器IP

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# 3. 上传代码（或 git clone）
cd /opt
git clone <你的仓库地址> LeBot2
cd LeBot2

# 4. 创建 .env 文件
nano .env

# 5. 启动
docker compose up -d

# 6. 查看日志
docker compose logs -f
```

---

## 常见问题

**Q: 报单没有被识别？**
A: 确保消息以 `a` 或 `A` 开头，如：`a d程`

**Q: 如何获取自己的用户 ID？**
A: 发送 `/id` 命令

**Q: 如何设置管理员？**
A: 超级管理员可以回复某人消息后发送 `/set_admin --global`

**Q: Bot 没有响应？**
A: 检查 Bot Token 是否正确，查看日志：`docker compose logs -f`

---

## 目录结构

```
LeBot2/
├── app/
│   ├── bot/          # Bot 核心逻辑
│   ├── models/       # 数据库模型
│   ├── services/     # 数据库服务
│   └── utils/        # 工具函数
├── data/             # 数据库文件（自动创建）
├── logs/             # 日志文件（自动创建）
├── main.py           # 程序入口
├── requirements.txt  # Python 依赖
├── docker-compose.yml
├── Dockerfile
└── .env              # 环境配置（需自行创建）
```

---

## 技术栈

- **FastAPI** - Web 框架
- **python-telegram-bot** - Telegram Bot API
- **SQLAlchemy** - ORM
- **SQLite** - 数据库
- **Uvicorn** - ASGI 服务器
