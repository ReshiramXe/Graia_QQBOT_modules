# Graia QQ Bot Modules

基于 Graia/Ariadne 框架的 QQ 机器人项目，支持多种 LLM 驱动的群聊/Friend 对话、Agent 模式（Tool Calling）以及联网搜索等功能。

## 项目结构

```
F:\PythonProject2\
├── modules/                       # 所有功能模块
│   ├── agent_mode.py              # Agent 模式 - LLM Tool Calling 核心
│   ├── ai_chat_group.py           # 群聊 AI 对话（@Bot 触发）
│   ├── ai_chat_friend.py          # 私聊 AI 对话
│   ├── config_loader.py           # 统一配置加载（数据库、API key 等）
│   ├── model_manager.py           # 模型管理（多 API 提供商）
│   ├── menu_handler.py / menu_manager.py  # 菜单系统
│   ├── date_input.py / date_deleter.py / date_deleter_legacy.py  # 日期提醒
│   ├── daily_date_reminder.py     # 每日提醒
│   ├── birthday_notifier.py       # 生日提醒
│   ├── timer_manager.py           # 定时器
│   ├── message_inserter.py        # 消息插入
│   ├── forward_message.py         # 消息转发
│   ├── music_searcher.py          # 音乐搜索
│   ├── text_to_image.py           # 文字转图片
│   ├── dice_roller.py             # 骰子
│   ├── petpet_avatar.py           # 头像相关
│   ├── tarot_reader.py            # 塔罗牌
│   ├── system_monitor.py          # 系统监控
│   └── ai_auto_reply.py           # 自动回复
```

## LLM 提供商

支持多个 OpenAI 兼容 API 端点，通过 `ai_bot_group.yaml` 配置：

- DeepSeek（默认）
- SiliconFlow
- X.AI (Grok)
- Kimi (Moonshot)
- 小爱 (xiaoai)
- 自定义 URL

## Agent 模式 (agent_mode.py)

管理员通过 `yb切换模式` / `yb结束模式` 控制。

开启后 @Bot 触发 Tool Calling，模型可自主调用以下工具：

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容 |
| `list_directory` | 浏览目录结构 |
| `search_files` | glob 模式搜索文件 |
| `sql_query` | 只读 SQL 查询 |
| `get_chat_history` | 读取群聊天记录 |
| `search_chat_history` | 搜索群聊天记录 |
| `get_user_impression_agent` | 查询用户印象 |
| `draw_tarot` | 抽取塔罗牌 |
| `list_tarot_cards` | 列出所有塔罗牌 |
| `web_search` | **联网搜索（DuckDuckGo，免费）** |

### 联网搜索

2026-06-09 新增 `web_search` 工具，使用 DuckDuckGo 免费搜索引擎。

- **依赖**: `duckduckgo_search` (pip install)
- **后端**: DuckDuckGo，无需 API Key，无调用次数限制
- **触发**: 当用户询问最新新闻、实时数据、天气等需要联网的信息时，DeepSeek 模型自动调用
- **返回**: 网页标题 + URL + 摘要（最多 5 条）

## 数据库

使用 MySQL (pymysql) 存储：

- `ai_config` / `ai_config_2` - AI 模型配置（按群/用户）
- `user_impressions` - 用户印象系统
- `group_settings` - 群设置（冷却时间等）
- `group_chat_messages` - 群聊消息记录（用于每日总结）
- 日期提醒、定时器等表

## 配置说明

所有配置文件位于 `modules/config/`，以 YAML 格式存储：

- `ai_bot_group.yaml` - 群聊 AI 配置（API keys、模型列表、prompt 等）
- `ai_bot_friend.yaml` - 私聊 AI 配置
- `agent_mode.yaml` - Agent 模式配置（LLM 设置、安全策略等）
- `common_config.yaml` - 公共配置（数据库连接等）
- 其他模块专属 YAML 配置

> ⚠️ 配置文件包含 API key 等敏感信息，已加入 .gitignore，不会提交到仓库。
