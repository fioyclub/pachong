# BC.Game足球赔率Telegram机器人

这是一个用于监控BC.Game足球1X2赔率的Telegram机器人，支持实时监控和批量获取赔率数据。

## 功能特性

- 🤖 **Telegram机器人控制** - 通过简单的命令控制爬虫
- 📊 **批量获取赔率** - 一次性获取所有当前足球1X2赔率
- 👁️ **实时监控** - 持续监控赔率变化并推送通知
- 💾 **内存管理** - 自动内存清理，防止OOM
- 👥 **多用户支持** - 支持多个用户同时使用
- 🔐 **权限控制** - 可配置允许使用的用户列表
- 🏥 **健康检查** - 内置健康检查端点，适合云部署

## 可用命令

- `/start` - 显示欢迎信息和快捷按钮
- `/odds` - 获取当前所有足球1X2赔率
- `/monitor` - 开始实时监控赔率变化
- `/stop` - 停止当前监控
- `/status` - 查看机器人运行状态
- `/memory` - 查看内存使用情况
- `/help` - 显示详细帮助信息

## 本地开发

### 环境要求

- Python 3.11+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的配置：
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USERS=123456789,987654321
```

### 运行机器人

```bash
python telegram_bot.py
```

## Render部署

### 1. 准备代码

1. 将代码推送到GitHub仓库
2. 确保所有文件都已提交

### 2. 在Render上创建服务

1. 登录 [Render](https://render.com)
2. 点击 "New" -> "Web Service"
3. 连接你的GitHub仓库
4. 配置服务：

**基本设置：**
- **Name**: `bc-game-telegram-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python telegram_bot.py`

**环境变量：**
```
TELEGRAM_BOT_TOKEN=你的机器人Token
ALLOWED_USERS=允许使用的用户ID列表（用逗号分隔）
PORT=10000
MAX_MEMORY_MB=450
MEMORY_CHECK_INTERVAL=300
MONITOR_INTERVAL=30
MAX_CONCURRENT_MONITORS=10
LOG_LEVEL=INFO
```

### 3. 获取Telegram Bot Token

1. 在Telegram中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取Token并填入环境变量

### 4. 获取用户ID

1. 在Telegram中找到 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息获取你的用户ID
3. 将用户ID填入 `ALLOWED_USERS` 环境变量

### 5. 部署

1. 点击 "Create Web Service"
2. 等待部署完成
3. 检查日志确认服务正常运行

## 项目结构

```
.
├── bc_game_monitor.py      # BC.Game监控模块
├── bc_game_scraper.py      # BC.Game爬虫模块
├── telegram_bot.py         # Telegram机器人主程序
├── health_server.py        # 健康检查服务器
├── requirements.txt        # Python依赖
├── Procfile               # Render部署配置
├── runtime.txt            # Python版本指定
├── .env.example           # 环境变量模板
└── README.md              # 项目说明
```

## 内存管理

机器人内置了多种内存管理机制：

- **自动内存清理** - 定期执行垃圾回收
- **内存监控** - 实时监控内存使用情况
- **OOM预防** - 内存使用过高时自动清理
- **数据清理** - 及时清理不需要的数据

## 注意事项

1. **Render免费计划限制**：
   - 内存限制512MB，建议设置 `MAX_MEMORY_MB=450`
   - 15分钟无活动会休眠，健康检查服务器可防止休眠
   - 每月750小时免费使用时间

2. **使用建议**：
   - 长时间监控建议定期重启
   - 避免同时运行过多监控任务
   - 定期检查内存使用情况

3. **故障排除**：
   - 检查Render日志查看错误信息
   - 确认环境变量配置正确
   - 验证Telegram Bot Token有效性

## 技术栈

- **Python 3.11** - 主要编程语言
- **python-telegram-bot** - Telegram机器人框架
- **aiohttp** - 异步HTTP客户端
- **Flask** - 健康检查Web服务器
- **psutil** - 系统监控
- **asyncio** - 异步编程支持

## 许可证

本项目仅供学习和研究使用。