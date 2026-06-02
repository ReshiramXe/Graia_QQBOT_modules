# Graia QQBot Modules

基于 [Graia Ariadne](https://github.com/GraiaProject/Ariadne) 框架的多功能 QQ 机器人模块集合，支持 AI 对话、塔罗牌占卜、音乐搜索、定时提醒等丰富功能。

## ✨ 功能模块

### 🤖 AI 对话
| 模块 | 说明 |
|------|------|
| `ai_chat_group.py` | 群聊 AI 对话，支持多平台 API（DeepSeek / SiliconFlow / xAI / Kimi / 小爱），印象系统，冷却管理 |
| `ai_chat_friend.py` | 好友私聊 AI 对话，支持语音回复，自定义人格 |
| `ai_auto_reply.py` | 概率触发的群聊自主回复，模拟自然参与感 |

### 🎴 娱乐功能
| 模块 | 说明 |
|------|------|
| `tarot_reader.py` | AI 塔罗牌占卜，随机抽牌并解读运势 |
| `dice_roller.py` | 骰子投掷 |
| `petpet_avatar.py` | 宠物头像生成（PetPet 动图） |
| `forward_message.py` | "群友说"转发模拟 |

### 🎵 音乐
| 模块 | 说明 |
|------|------|
| `music_searcher.py` | 音乐搜索与播放（支持语音消息发送） |

### ⏰ 提醒与管理
| 模块 | 说明 |
|------|------|
| `timer_manager.py` | 定时提醒管理（新增/修改/删除/查询） |
| `birthday_notifier.py` | 生日自动提醒 |
| `daily_date_reminder.py` | 每日日期提醒 |
| `date_input.py` | 日期录入 |
| `date_deleter.py` / `date_deleter_legacy.py` | 日期删除 |

### 🛠 系统工具
| 模块 | 说明 |
|------|------|
| `system_monitor.py` | 系统状态查询（CPU/内存/磁盘/网络/运行时间） |
| `config_loader.py` | 统一配置加载模块 |
| `model_manager.py` | AI 模型配置管理 |
| `menu_handler.py` / `menu_manager.py` | 功能菜单管理 |
| `message_inserter.py` | 消息插入 |
| `text_to_image.py` | 文字转图片 |

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

## 📄 许可证

本项目仅用于学习和研究目的。使用前请确保遵守相关服务条款。

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
