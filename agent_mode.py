# Agent 模式模块
# 管理员可通过 yb切换模式 / yb结束模式 控制
# 开启后 @Bot 使用 tool-calling 自主调用文件系统和数据库


import json
import re
import glob as glob_module
import yaml
import pymysql
import logging
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import DetectPrefix

channel = Channel.current()
logger = logging.getLogger(__name__)

# ============================================================
# 配置加载
# ============================================================

def load_config():
    config_path = Path(__file__).parent / 'config' / 'agent_mode.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

# 触发指令
CMD_ENABLE = config['commands']['enable']
CMD_DISABLE = config['commands']['disable']

# 回复文案
MSG = config['messages']

# 管理员
ADMIN_USERS = set(config.get('admin_users', []))

# 人格设定
PERSONA_BASE = config['persona']['base']
PERSONA_CTX_TPL = config['persona']['context_template']

# LLM 配置
LLM = config['llm']
LLM_MODEL = LLM['model']
LLM_TEMPERATURE = LLM.get('temperature', 0.3)
LLM_MAX_TOKENS = LLM.get('max_tokens', 4096)
LLM_MAX_ITER = LLM.get('max_iterations', 10)

# 数据库配置
DB_CONFIG = config.get('database', {})

# 安全配置
SEC = config['security']
ALLOWED_DIRS_RAW = SEC.get('allowed_directories', ['.'])
DISALLOWED_EXT = set(
    (ext if ext.startswith('.') else f'.{ext}').lower()
    for ext in SEC.get('disallowed_extensions', [])
)
MAX_FILE_SIZE = SEC.get('max_file_size_bytes', 1_048_576)
MAX_SQL_ROWS = SEC.get('max_sql_rows', 100)

# 解析允许目录为绝对路径
PROJECT_ROOT = Path(__file__).parent.resolve()
ALLOWED_DIRS = []
for d in ALLOWED_DIRS_RAW:
    p = Path(d)
    p = (PROJECT_ROOT / d).resolve() if not p.is_absolute() else p.resolve()
    ALLOWED_DIRS.append(p)

# AsyncOpenAI 客户端
aclient = AsyncOpenAI(
    api_key=LLM['api_key'],
    base_url=LLM['base_url'],
)

# ============================================================
# Agent 模式状态管理
# ============================================================

agent_mode_groups: set[int] = set()


def is_agent_mode(group_id: int) -> bool:
    """供 ai_chat_group.py 调用，检查该群是否开启了 agent 模式"""
    return group_id in agent_mode_groups


# ============================================================
# 监听器: 切换模式
# ============================================================

@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix(CMD_ENABLE)]
    )
)
async def enable_agent_mode(app: Ariadne, group: Group, member: Member):
    if member.id not in ADMIN_USERS:
        await app.send_message(group, MessageChain([Plain(MSG['no_permission'])]))
        return
    if group.id in agent_mode_groups:
        await app.send_message(group, MessageChain([Plain(MSG['already_enabled'])]))
        return
    agent_mode_groups.add(group.id)
    await app.send_message(group, MessageChain([Plain(MSG['mode_enabled'])]))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix(CMD_DISABLE)]
    )
)
async def disable_agent_mode(app: Ariadne, group: Group, member: Member):
    if member.id not in ADMIN_USERS:
        await app.send_message(group, MessageChain([Plain(MSG['no_permission'])]))
        return
    if group.id not in agent_mode_groups:
        await app.send_message(group, MessageChain([Plain(MSG['already_disabled'])]))
        return
    agent_mode_groups.discard(group.id)
    await app.send_message(group, MessageChain([Plain(MSG['mode_disabled'])]))


# ============================================================
# 安全检查
# ============================================================

def _is_path_allowed(target_path: Path) -> bool:
    try:
        resolved = target_path.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    for allowed in ALLOWED_DIRS:
        try:
            resolved.relative_to(allowed)
            return True
        except ValueError:
            continue
    return False


def _is_extension_disallowed(target_path: Path) -> bool:
    return target_path.suffix.lower() in DISALLOWED_EXT


def _is_safe_to_read(target_path: Path) -> tuple:
    path = Path(target_path)
    if not path.exists():
        return False, f"路径不存在: {target_path}"
    if not path.is_file():
        return False, f"路径不是文件: {target_path}"
    if not _is_path_allowed(path):
        return False, f"路径不在允许的目录范围内"
    if _is_extension_disallowed(path):
        return False, f"文件类型不允许访问: {path.suffix}"
    try:
        size = path.stat().st_size
    except OSError as e:
        return False, f"无法获取文件信息: {e}"
    if size > MAX_FILE_SIZE:
        return False, f"文件过大: {size} 字节 (最大 {MAX_FILE_SIZE})"
    return True, ""


def _detect_encoding(file_path: Path) -> str:
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw = f.read(8192)
        result = chardet.detect(raw)
        return result.get('encoding', 'utf-8') or 'utf-8'
    except ImportError:
        for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read(1024)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return 'utf-8'


# ============================================================
# 工具实现
# ============================================================

async def tool_read_file(path: str) -> str:
    file_path = Path(path)
    file_path = (PROJECT_ROOT / path).resolve() if not file_path.is_absolute() else file_path.resolve()

    safe, reason = _is_safe_to_read(file_path)
    if not safe:
        return f"[错误] {reason}"

    encoding = _detect_encoding(file_path)
    for enc in [encoding, 'gbk', 'gb2312', 'latin-1', 'utf-8']:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return f"[错误] 无法解码文件内容"

    if len(content) > MAX_FILE_SIZE:
        content = content[:MAX_FILE_SIZE] + "\n\n... [内容已截断]"
    return content


async def tool_list_directory(path: str) -> str:
    dir_path = Path(path)
    dir_path = (PROJECT_ROOT / path).resolve() if not dir_path.is_absolute() else dir_path.resolve()

    if not _is_path_allowed(dir_path):
        return f"[错误] 目录不在允许的范围内"
    if not dir_path.exists():
        return f"[错误] 目录不存在"
    if not dir_path.is_dir():
        return f"[错误] 不是目录"

    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return f"[错误] 没有权限访问目录"
    except OSError as e:
        return f"[错误] 无法读取目录: {e}"

    truncated = len(entries) > MAX_SQL_ROWS
    if truncated:
        entries = entries[:MAX_SQL_ROWS]

    lines = []
    for e in entries:
        t = "DIR" if e.is_dir() else "FILE"
        try:
            s = e.stat().st_size
        except OSError:
            s = 0
        lines.append(f"  [{t}] {e.name} ({s:,} bytes)")

    result = f"目录 '{dir_path}' ({len(entries)} 项):\n" + "\n".join(lines)
    if truncated:
        result += f"\n\n... [已截断，最多 {MAX_SQL_ROWS} 项]"
    return result


async def tool_search_files(pattern: str) -> str:
    search_root = str(PROJECT_ROOT)
    full_pattern = str(PROJECT_ROOT / "**" / pattern)

    try:
        matches = glob_module.glob(full_pattern, recursive=True)
    except Exception as e:
        return f"[错误] 搜索模式无效: {e}"

    filtered = []
    for m in matches:
        mp = Path(m)
        if not _is_path_allowed(mp) or _is_extension_disallowed(mp):
            continue
        filtered.append(mp)

    truncated = len(filtered) > MAX_SQL_ROWS
    if truncated:
        filtered = filtered[:MAX_SQL_ROWS]

    if not filtered:
        return f"未找到匹配 '{pattern}' 的文件"

    lines = []
    for f in filtered:
        try:
            s = f.stat().st_size
        except OSError:
            s = 0
        rel = f.relative_to(PROJECT_ROOT)
        lines.append(f"  {rel} ({s:,} bytes)")

    result = f"搜索 '{pattern}' 找到 {len(filtered)} 个文件:\n" + "\n".join(lines)
    if truncated:
        result += f"\n\n... [已截断，最多 {MAX_SQL_ROWS} 个]"
    return result


async def tool_sql_query(query: str) -> str:
    # 安全检查: 仅允许 SELECT
    cleaned = query.strip().rstrip(';').strip()
    if not re.match(r'^SELECT\b', cleaned, re.IGNORECASE):
        return "[错误] 仅允许 SELECT 查询"

    dangerous = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
                 'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE']
    for word in dangerous:
        if re.search(rf'\b{word}\b', cleaned, re.IGNORECASE):
            return f"[错误] 检测到危险操作: {word}"

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(cleaned + " LIMIT " + str(MAX_SQL_ROWS))
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description] if cursor.description else []
    except pymysql.MySQLError as e:
        return f"[错误] 数据库查询失败: {e}"

    if not rows:
        return "查询结果为空"

    result = []
    for row in rows:
        result.append(dict(zip(cols, [str(v) if v is not None else None for v in row])))

    return json.dumps(result, ensure_ascii=False, indent=2)


async def tool_get_chat_history(group_id: int, count: int = 20) -> str:
    """读取指定群的最近聊天消息记录"""
    count = min(count, MAX_SQL_ROWS)
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT member_name, message_text, message_time
                         FROM group_chat_messages
                         WHERE group_id = %s
                         ORDER BY message_time DESC
                         LIMIT %s"""
                cursor.execute(sql, (group_id, count))
                rows = cursor.fetchall()
    except pymysql.MySQLError as e:
        return f"[错误] 查询失败: {e}"

    if not rows:
        return f"群 {group_id} 暂无聊天记录"

    lines = [f"群 {group_id} 最近 {len(rows)} 条消息:"]
    for name, text, t in reversed(rows):
        time_str = str(t) if t else ""
        lines.append(f"  [{time_str}] {name}: {text}")
    return "\n".join(lines)


async def tool_search_chat_history(group_id: int, keyword: str, count: int = 20) -> str:
    """按关键词搜索群聊历史消息"""
    count = min(count, MAX_SQL_ROWS)
    like = f"%{keyword}%"
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT member_name, message_text, message_time
                         FROM group_chat_messages
                         WHERE group_id = %s AND message_text LIKE %s
                         ORDER BY message_time DESC
                         LIMIT %s"""
                cursor.execute(sql, (group_id, like, count))
                rows = cursor.fetchall()
    except pymysql.MySQLError as e:
        return f"[错误] 搜索失败: {e}"

    if not rows:
        return f"群 {group_id} 中未找到包含 '{keyword}' 的消息"

    lines = [f"搜索 '{keyword}' 在群 {group_id} 找到 {len(rows)} 条:"]
    for name, text, t in reversed(rows):
        time_str = str(t) if t else ""
        lines.append(f"  [{time_str}] {name}: {text}")
    return "\n".join(lines)


async def tool_get_user_impression(user_id: int, group_id: int) -> str:
    """查询指定用户的印象"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT impression
                         FROM user_impressions
                         WHERE user_id = %s AND group_id = %s"""
                cursor.execute(sql, (user_id, group_id))
                result = cursor.fetchone()
                if result:
                    return f"用户 {user_id} 在群 {group_id} 的印象: {result[0]}"
                return f"用户 {user_id} 在群 {group_id} 暂无印象记录"
    except pymysql.MySQLError as e:
        return f"[错误] 查询失败: {e}"


# ============================================================
# 工具定义 (OpenAI Function Calling Schema)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件的内容。传入文件路径（相对或绝对），返回文件文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，如 'config/xxx.yaml' 或 'ai_chat_group.py'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出目录下的所有文件和子目录。用于浏览文件系统结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出内容的目录路径，如 'config' 或 '.'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "使用 glob 模式递归搜索文件。如 '*.py' 搜索所有 Python 文件，'config/*.yaml' 搜索 config 下的 YAML。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "glob 搜索模式，如 '*.py'、'*.yaml'、'config/*'"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "执行只读 SQL 查询。仅支持 SELECT 语句，自动限制返回行数。可查询的表包括 qqbotdate(日期提醒)、dallytime(定时)、ai_config(AI配置)、user_impressions(用户印象)、group_settings(群设置)、group_chat_messages(消息记录) 等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SELECT 查询语句，如 'SELECT COUNT(*) FROM dallytime'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_chat_history",
            "description": "读取指定群的最近聊天消息记录。用于了解群友在聊什么。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "要查询的群号"
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回的消息条数，默认 20，最多 100"
                    }
                },
                "required": ["group_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_chat_history",
            "description": "按关键词搜索群聊历史消息。用于查找群友之前讨论过的内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "要搜索的群号"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回的消息条数，默认 20，最多 100"
                    }
                },
                "required": ["group_id", "keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_impression_agent",
            "description": "查询指定用户在群内的印象记录。用于了解某个群友的性格特点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "要查询的用户 QQ ID"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "群号"
                    }
                },
                "required": ["user_id", "group_id"]
            }
        }
    }
]

TOOL_MAP = {
    "read_file": tool_read_file,
    "list_directory": tool_list_directory,
    "search_files": tool_search_files,
    "sql_query": tool_sql_query,
    "get_chat_history": tool_get_chat_history,
    "search_chat_history": tool_search_chat_history,
    "get_user_impression_agent": tool_get_user_impression,
}


# ============================================================
# 用户印象查询（复用 ai_chat_group.py 的数据库逻辑）
# ============================================================

async def get_user_impression(user_id: int, group_id: int) -> str:
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = "SELECT impression FROM user_impressions WHERE user_id = %s AND group_id = %s"
                cursor.execute(sql, (user_id, group_id))
                result = cursor.fetchone()
                return result[0] if result else "暂无印象"
    except pymysql.MySQLError:
        return "暂无印象"


# ============================================================
# Agent 循环
# ============================================================

async def run_agent_chat(
    user_input: str,
    group_id: int,
    member_id: int,
    member_name: str
) -> str:
    """
    Agent 模式下的对话处理。
    由 ai_chat_group.py 在检测到 agent 模式时调用。
    返回 LLM 的最终文本回复。
    """
    # 获取用户印象
    impression = await get_user_impression(member_id, group_id)

    # 构建 system prompt
    system_prompt = PERSONA_BASE + PERSONA_CTX_TPL.format(
        group_id=group_id,
        member_name=member_name,
        member_id=member_id,
        impression=impression,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]

    for iteration in range(LLM_MAX_ITER):
        try:
            response = await aclient.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            logger.error(f"Agent API error at iteration {iteration+1}: {e}")
            return MSG['api_error']

        choice = response.choices[0]
        msg = choice.message

        # 无 tool_calls → 最终回复
        if msg.content and not msg.tool_calls:
            return msg.content

        # 有 tool_calls → 执行并反馈
        if msg.tool_calls:
            # 追加 assistant 消息（含 tool_calls）
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            })

            # 逐个执行工具
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_func = TOOL_MAP.get(tool_name)

                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_result = f"[错误] 参数解析失败: {tc.function.arguments}"
                else:
                    if tool_func is None:
                        tool_result = f"[错误] 未知工具: {tool_name}"
                    else:
                        try:
                            tool_result = await tool_func(**args)
                        except Exception as e:
                            tool_result = f"[错误] 执行失败 ({tool_name}): {e}"
                            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

            continue

        # 空响应（既无 content 也无 tool_calls）
        return MSG['api_error']

    # 超过最大迭代
    return MSG['timeout']
