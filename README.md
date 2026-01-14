# LeBot2 - Telegram智能算价机器人

基于 FastAPI + python-telegram-bot 的 Telegram 智能算价机器人。

## 功能特性

- 📦 自动识别订单中的价格信息
- 🧊 支持算式计算（如：`总60*2+60+6=186`）
- 👥 按群组独立管理账单
- 🔐 权限管理（普通用户/管理员/超级管理员）
- ➕➖ 管理员可调整账单金额
- 🗑️ 清账功能（删除历史数据，防止数据库膨胀）
- 🔒 a/A 前缀触发，避免日常聊天误识别

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 从 @BotFather 获取
BOT_TOKEN=your_bot_token_here

# 从 @userinfobot 获取你的ID
SUPER_ADMIN_IDS=123456789
```

### 3. 运行

```bash
python main.py
```

或使用 uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 使用方法

### 报单格式

在订单内容前加 `a` 或 `A` 前缀：

```
a d程
13045201820
黑龙江省齐齐哈尔市依安县依安镇翰林新居六栋一单元

雪茄鸭嘴兽 铁观音 绿豆 备选龙井
高维 绿豆 备选蓝莓
总186
```

### 指令列表

| 指令 | 说明 |
|------|------|
| `/start` | 开始使用 |
| `/bill` 或 `/账单` | 查看当前账单 |
| `/history` | 查看账单历史 |
| `/help` | 显示帮助 |
| `+100` | 增加账单（管理员） |
| `-100` | 减少账单（管理员） |
| `清账` | 清空账单和历史数据（管理员） |

## 项目结构

```
LeBot2/
├── app/
│   ├── bot/           # Bot相关
│   ├── services/      # 服务层（解析、数据库操作）
│   ├── models/        # 数据模型
│   ├── api/           # API路由
│   └── utils/         # 工具类
├── data/              # 数据库文件
├── logs/              # 日志文件
├── main.py            # 入口文件
└── requirements.txt   # 依赖包
```

## 技术栈

- FastAPI - Web框架
- python-telegram-bot - Telegram Bot API
- SQLAlchemy - ORM
- SQLite - 数据库
- Pydantic - 数据验证

## License

MIT
