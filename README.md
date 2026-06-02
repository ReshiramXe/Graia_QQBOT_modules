# Graia QQBot Modules

基于 [Graia Ariadne](https://github.com/GraiaProject/Ariadne) 框架的多功能 QQ 机器人模块集合，支持 AI 对话、塔罗牌占卜、音乐搜索、定时提醒等丰富功能。

## ✨ 功能模块与触发指令

### 🤖 AI 对话

| 指令 | 说明 | 模块 |
|------|------|------|
| `@Bot <消息>` | 群聊 AI 对话（@机器人触发） | `ai_chat_group.py` |
| `yb创建ai` | 创建当前群的 AI 配置 | `ai_chat_group.py` |
| `yb修改模型` | 修改 AI 模型（交互式选择） | `ai_chat_group.py` |
| `yb修改人格` | 修改 AI 人格/提示词 | `ai_chat_group.py` |
| `yb修改温度` | 修改 AI 温度参数 (0-2) | `ai_chat_group.py` |
| `yb修改url` | 修改 AI API 服务商 | `ai_chat_group.py` |
| `yb查询ai` | 查询当前群的 AI 配置 | `ai_chat_group.py` |
| `yb查询token` | 查询当日 token 用量 | `ai_chat_group.py` |
| `yb查询全群token` | 查询所有群 token 总用量 | `ai_chat_group.py` |
| `yb设置冷却时间` | 设置群聊 AI 回复冷却（秒） | `ai_chat_group.py` |
| `yb查询冷却时间` | 查询当前冷却时间 | `ai_chat_group.py` |
| `yb清除记忆` | 清除当前群对话记忆 | `ai_chat_group.py` |
| `yb查询印象` | 查询你的用户印象 | `ai_chat_group.py` |
| `yb反转印象` | 反转你的用户印象 | `ai_chat_group.py` |
| `yb清除印象` | 清除你的用户印象 | `ai_chat_group.py` |
| `yb清除全群印象` | 清除全群用户印象（管理员） | `ai_chat_group.py` |
| `yb查询好感排行` | 查看群内好感度排行 | `ai_chat_group.py` |
| `yb查询模型` | 查询所有平台可用模型列表 | `model_manager.py` |
| 好友私聊消息 | 好友直接发消息触发 AI 对话 | `ai_chat_friend.py` |
| *群内随机触发* | 概率触发自主回复（需配置） | `ai_auto_reply.py` |

### 🎴 娱乐功能

| 指令 | 说明 | 模块 |
|------|------|------|
| `yb抽塔罗牌` | 随机抽取塔罗牌，AI 解读运势 | `tarot_reader.py` |
| `yb添加塔罗牌图片 <牌名> [图片]` | 添加自定义塔罗牌图片 | `tarot_reader.py` |
| `yb塔罗牌列表` | 查看可用塔罗牌列表 | `tarot_reader.py` |
| `.rd [表达式]` | 骰子投掷，如 `.rd d20` `.rd 2d6+3` `.rd d100` | `dice_roller.py` |
| `yb摸摸 <@用户>` | 生成 PetPet 摸摸动图 | `petpet_avatar.py` |
| `群友说 <内容>` | 模拟多位群友转发该内容 | `forward_message.py` |

### 🎵 音乐

| 指令 | 说明 | 模块 |
|------|------|------|
| `来点宝音 <关键词>` | 搜索并播放音乐（语音消息） | `music_searcher.py` |
| `随机宝音` | 播放随机推荐音乐 | `music_searcher.py` |

### ⏰ 定时与提醒

| 指令 | 说明 | 模块 |
|------|------|------|
| `yb定时` | 交互式新增定时提醒 | `timer_manager.py` |
| `yb定时列表` | 查看当前群的定时列表 | `timer_manager.py` |
| `yb定时新增 <群号> "消息" <HH:MM>` | 跨群新增定时提醒（管理员） | `timer_manager.py` |
| `yb定时修改 <ID> 内容 <消息> 时间 <HH:MM>` | 修改已有定时 | `timer_manager.py` |
| `yb定时删除 <ID>` | 删除指定定时 | `timer_manager.py` |
| `yb定时查询` | 查询当前群所有定时 | `date_deleter_legacy.py` |
| `yb帮助定时` | 查看定时功能帮助 | `timer_manager.py` |
| `yb加入日期 <名字> <MMDD>` | 录入生日/纪念日 | `date_input.py` |
| `yb删除日期` | 删除日期记录 | `date_deleter.py` |
| `yb完整日期` | 查看完整日期列表 | `date_deleter.py` |
| `临近日期` | 查看临近的特殊日期 | `daily_date_reminder.py` |
| *每日 00:00 自动推送* | 当天生日的自动提醒 | `birthday_notifier.py` |

### 🛠 系统与菜单

| 指令 | 说明 | 模块 |
|------|------|------|
| `yb查询状态` | 查询服务器系统状态（CPU/内存/磁盘/余额） | `system_monitor.py` |
| `叶布功能` | 显示功能菜单（文字转图片） | `text_to_image.py` |
| `叶布功能w` | 显示功能菜单（文字，40秒后自动撤回） | `menu_handler.py` |
| `功能加入` | 菜单管理（管理员交互式操作） | `menu_manager.py` |

### 📝 骰子表达式格式

```
.rd          → 投掷 d100
.rd d20      → 投掷 1 个 20 面骰
.rd 2d6      → 投掷 2 个 6 面骰
.rd 2d6+3    → 投掷 2 个 6 面骰并 +3
.rd 4d6-2    → 投掷 4 个 6 面骰并 -2
```

## 🚀 快速开始

### 环境要求

- Python 3.9+
- MySQL / MariaDB 数据库
- 至少一个兼容 OpenAI API 的 LLM 服务（推荐 [DeepSeek](https://platform.deepseek.com/)）

### 安装

```bash
git clone https://github.com/ReshiramXe/Graia_QQBOT_modules.git
cd Graia_QQBOT_modules
pip install -r requirements.txt
```

### 配置

1. 在 `config/` 目录下，参考 `*.example.yaml` 模板创建对应的配置文件：

```bash
# 创建通用配置（数据库 + API 密钥）
cp config/common_config.example.yaml config/common_config.yaml

# 创建群聊 AI 配置
cp config/ai_bot_group.example.yaml config/ai_bot_group.yaml

# 根据需要创建其他模块配置...
```

2. 编辑各 `.yaml` 文件，填入你的数据库连接信息、API 密钥等：

```yaml
# config/common_config.yaml 示例
database:
  host: "127.0.0.1"
  user: "root"
  passwd: "your_db_password"
  port: 3306
  db: "qqbot"
  charset: "utf8mb4"

api_keys:
  deepseek: "sk-your-deepseek-api-key"
  # ... 其他 API 密钥
```

3. 确保 MySQL 数据库已创建并导入所需表结构。

### 运行

将模块放入你的 Graia Ariadne 机器人项目的 `modules/` 目录，或通过 Saya 加载。

## 📦 主要依赖

| 依赖 | 用途 |
|------|------|
| [Graia Ariadne](https://github.com/GraiaProject/Ariadne) | QQ 机器人框架 |
| [Graia Saya](https://github.com/GraiaProject/Saya) | 模块化管理 |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | LLM API 调用 |
| [PyMySQL](https://github.com/PyMySQL/PyMySQL) | MySQL 数据库连接 |
| [graiax-silkcoder](https://github.com/GraiaProject/graiax-silkcoder) | 语音消息编码 |
| [Pillow](https://python-pillow.org/) | 图片处理 |
| [psutil](https://github.com/giampaolo/psutil) | 系统监控 |
| [Selenium](https://www.selenium.dev/) | 音乐搜索（可选） |

## 🔧 数据库表结构

部分模块依赖以下 MySQL 表：

```sql
-- 日期提醒
CREATE TABLE qqbotdate (name VARCHAR(255), date VARCHAR(4));

-- 定时提醒
CREATE TABLE dallytime (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id BIGINT,
    group_id BIGINT,
    message TEXT,
    time_created TIME
);

-- AI 配置
CREATE TABLE ai_config (
    qq_group_id BIGINT PRIMARY KEY,
    ai_model_name VARCHAR(255),
    ai_prompt_content TEXT,
    temperature DECIMAL(3,2),
    url VARCHAR(255)
);

-- 用户印象
CREATE TABLE user_impressions (
    user_id BIGINT,
    group_id BIGINT,
    impression TEXT,
    PRIMARY KEY (user_id, group_id)
);
```

## ⚠️ 注意事项

- 所有敏感信息（API 密钥、数据库密码等）存放在 `config/*.yaml` 中，这些文件已被 `.gitignore` 排除，不会被提交到仓库
- 首次使用请先复制 `.example.yaml` 模板并填入真实配置
- 不同模块的 AI 功能可配置使用不同的 LLM 提供商
- 音乐搜索模块使用第三方 API，请确保你有合法的访问权限
- `@Bot` 触发需要在配置中设置正确的 `bot_self_id`

## 📄 许可证

本项目仅用于学习和研究目的。使用前请确保遵守相关服务条款。

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
