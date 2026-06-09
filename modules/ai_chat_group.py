# 机叶的群聊功能
import json
import yaml
from collections import defaultdict
import transformers
from openai import OpenAI
from pathlib import Path
import asyncio
import re
import pymysql
import random
import httpx
from typing import Optional
import graiax.silkcoder as silkcoder
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage, FriendMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image, Voice, Plain, At, Forward, ForwardNode
from graia.ariadne.model import Group, Member, Friend
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from datetime import datetime, date
import time
from graia.saya import Saya
from openai import AsyncOpenAI
from graia.ariadne.message.parser.base import DetectPrefix
from graia.ariadne.message.parser.base import MatchContent
from graia.broadcast.interrupt import InterruptControl
from creart import create
from graia.scheduler.saya import SchedulerSchema
from graia.scheduler import timers
from modules.agent_mode import is_agent_mode, run_agent_chat

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config' / 'ai_bot_group.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


channel = Channel.current()
saya = Saya.current()
chat_histories = {}
cooldown_records = {}
model_settings = {}
inc = create(InterruptControl)
message_counters = defaultdict(lambda: defaultdict(int))
daily_token_usage = defaultdict(int)
chat_tokenizer_dir = "./"
INPUT_PATTERN = r"^\s*([^+]+?)\s*\+\s*'(.*?)'\s*\+\s*([01](\.\d+)?|2(\.0+)?)\s*$"

config = load_config()
DB_CONFIG = config.get('database', {})
ALLOWED_USERS = set(config.get('allowed_users', []))
PROXY_CONFIG = config.get('proxy', {})

# 从配置加载敏感标识符
BOT_SELF_ID = str(config.get('bot_self_id', '0'))
ADMIN_USER_IDS = set(config.get('admin_user_ids', []))
PRIVILEGED_USER_IDS = set(config.get('privileged_user_ids', []))
DEEPSEEK_GROUPS = set(config.get('deepseek_groups', []))
SPECIAL_COOLDOWN_USERS = config.get('special_cooldown_users', {})
VOICE_FILE_PATH = config.get('voice_file', 'data/voices/default.mp3')

try:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        chat_tokenizer_dir,
        trust_remote_code=True,
        local_files_only=True
    )

    # 确保tokenizer有正确的encode方法
    if not hasattr(tokenizer, 'encode'):
        raise Exception("Tokenizer does not have encode method")

except Exception as e:
    print(f"Tokenizer初始化失败: {e}")

    # 使用tiktoken作为备选方案（需要安装：pip install tiktoken）
    try:
        import tiktoken

        tokenizer = tiktoken.get_encoding("cl100k_base")  # 使用OpenAI的编码
        print("使用tiktoken作为备选tokenizer")
    except ImportError:
        print("tiktoken未安装，使用简单字符计数")


        # 更准确的备选方案：字符数除以4（近似token估算）
        class SimpleTokenizer:
            def encode(self, text):
                # 返回字符列表作为近似
                return list(text)


        tokenizer = SimpleTokenizer()

clients = {
    "siliconflow": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['siliconflow'],
            base_url="https://api.siliconflow.cn/v1"
        )
    },
    "deepseek": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['deepseek'],
            base_url="https://api.deepseek.com/v1"
        )
    },
    "xiaoai": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['xiaoai'],
            base_url="https://xiaoai.plus/v1"
        )
    },
    "xi-ai": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['xi-ai'],
            base_url="https://api.xi-ai.cn/v1/"
        )
    },
    "xai": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['xai'],
            base_url="https://api.x.ai/v1"
        )
    },
    "Kimi": {
        "instance": AsyncOpenAI(
            api_key=config['api_keys']['Kimi'],
            base_url="https://api.moonshot.cn/v1"
        )
    },
}

ai_prompt_content_0 = config['ai_prompt01']


# === 印象系统开始 ===

async def get_user_impression(user_id: int, group_id: int) -> str:
    """获取用户印象"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT impression
                          FROM user_impressions
                          WHERE user_id = %s AND group_id = %s"""
                cursor.execute(sql, (user_id, group_id))
                result = cursor.fetchone()
                return result[0] if result else "暂无印象"
    except pymysql.MySQLError:
        return "暂无印象"


async def update_user_impression(user_id: int, group_id: int, new_impression: str):
    """更新用户印象"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """INSERT INTO user_impressions (user_id, group_id, impression)
                         VALUES (%s, %s, %s)
                         ON DUPLICATE KEY UPDATE impression = %s"""
                cursor.execute(sql, (user_id, group_id, new_impression, new_impression))
                conn.commit()
    except pymysql.MySQLError as e:
        print(f"更新用户印象失败: {e}")


async def generate_impression_update(current_impression: str, conversation: list) -> str:
    """生成新的用户印象"""
    try:
        client = clients["deepseek"]["instance"]
        messages = [
            {
                "role": "system",
                "content": config['generate_impression_update_prompt']
            },
            {
                "role": "user",
                "content": f"当前印象: {current_impression}\n"
                           f"对话历史:\n{conversation[-2:]}\n\n"
                           "请生成更新后的用户印象:"
            }
        ]
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return current_impression


async def reverse_impression_text(impression_text: str) -> str:
    """使用AI API反转印象文本和分数"""
    try:
        client = clients["deepseek"]["instance"]
        messages = [
            {
                "role": "system",
                "content": config['reverse_impression_text']
            },
            {
                "role": "user",
                "content": f"请反转以下印象：\n{impression_text}"
            }
        ]

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI反转印象失败: {e}")
        return impression_text  # 失败时返回原印象


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb反转印象")]
    )
)
async def reverse_impression(app: Ariadne, group: Group, member: Member, message: MessageChain):
    # await app.send_message(
    #     group,
    #     MessageChain([
    #         At(member.id),
    #         Plain("\n为了节省资源,已关闭此功能\n请注重每一句话的重量")
    #     ])
    # )
    try:

        current_impression = await get_user_impression(member.id, group.id)

        if current_impression == "暂无印象":
            return await app.send_message(group, MessageChain("无印象可反转啊!"))

        reversed_impression = await reverse_impression_text(current_impression)
        if reversed_impression == current_impression:
            return await app.send_message(group, MessageChain("反转失败"))

        # 更新数据库
        await update_user_impression(member.id, group.id, reversed_impression)
        reset_memory(group.id)

        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain(" 印象逆转完成")
            ])
        )
    except Exception as e:
        await app.send_message(group, MessageChain(f"反转印象失败: {str(e)}"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb清除全群印象")]
    )
)
async def clear_impression(app: Ariadne, group: Group, member: Member, message: MessageChain):
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有几位可执行此操作"))

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = "DELETE FROM user_impressions WHERE group_id = %s"
                cursor.execute(sql, (group.id,))
                conn.commit()
        await app.send_message(group, MessageChain("已清除全群印象"))
    except Exception as e:
        await app.send_message(group, MessageChain(f"清除印象失败: {str(e)}"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb清除印象")]
    )
)
async def clear_impression(app: Ariadne, group: Group, member: Member, message: MessageChain):
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = "DELETE FROM user_impressions WHERE group_id = %s AND user_id = %s"
                cursor.execute(sql, (group.id, member.id))
                conn.commit()
        await app.send_message(group, MessageChain(f"已清除印象"))
    except Exception as e:
        await app.send_message(group, MessageChain(f"清除印象失败: {str(e)}"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb查询印象")]
    )
)
async def query_my_impression(app: Ariadne, group: Group, member: Member):
    try:
        impression = await get_user_impression(member.id, group.id)
        response = f"印象档案:\n{impression}"
        # response = "咘咿~"
        fwd_nodeList = [
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(response),
            )
        ]
        message = MessageChain(Forward(nodeList=fwd_nodeList))
        await app.send_message(group, message)
    except Exception as e:
        await app.send_message(
            group,
            MessageChain(f"查询印象失败: {str(e)}"))


# 清除记忆
def reset_memory(group_id):
    if group_id in chat_histories:
        del chat_histories[group_id]


async def get_group_cooldown(group_id):
    """获取群聊的冷却时间设置"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                # 检查并创建group_settings表
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id BIGINT PRIMARY KEY,
                    cooldown_time INT NOT NULL DEFAULT 86400
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                cursor.execute(create_table_sql)

                # 查询冷却时间
                sql = """SELECT cooldown_time FROM group_settings WHERE group_id = %s"""
                cursor.execute(sql, (group_id,))
                result = cursor.fetchone()
                return result[0] if result else 86400  # 默认24小时
    except pymysql.MySQLError:
        return 86400  # 数据库错误时使用默认值


async def set_group_cooldown(group_id, cooldown_time):
    """设置群聊的冷却时间"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                # 检查并创建group_settings表
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id BIGINT PRIMARY KEY,
                    cooldown_time INT NOT NULL DEFAULT 86400
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                cursor.execute(create_table_sql)

                # 插入或更新冷却时间
                sql = """INSERT INTO group_settings (group_id, cooldown_time)
                         VALUES (%s, %s)
                         ON DUPLICATE KEY UPDATE cooldown_time = %s"""
                cursor.execute(sql, (group_id, cooldown_time, cooldown_time))
                conn.commit()
                return True, None
    except pymysql.MySQLError as e:
        error_msg = f"数据库错误: {e}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"系统错误: {str(e)}"
        print(error_msg)
        return False, error_msg


# === 印象系统结束 ===

# === token 系统开始 ===
def calculate_token_count(text):
    if not text:
        return 0
    result = tokenizer.encode(text)
    print(result)
    return len(result)


def get_user_key(group_id, member_id):
    return f"{group_id}_{member_id}"


async def update_daily_token_usage(group_id, member_id, user_input, bot_response):
    if not member_id:  # 如果没有用户ID，无法跟踪
        return

    # 计算输入和输出的token总数
    input_tokens = calculate_token_count(user_input)
    output_tokens = calculate_token_count(bot_response)
    total_tokens = input_tokens + output_tokens

    # 更新token使用量
    user_key = get_user_key(group_id, member_id)
    daily_token_usage[user_key] += total_tokens

    print(
        f"用户 {member_id} 在群 {group_id} 消耗了 {total_tokens} tokens (输入: {input_tokens}, 输出: {output_tokens})")


def get_daily_token_usage(group_id, member_id):
    user_key = get_user_key(group_id, member_id)
    return daily_token_usage.get(user_key, 0)


def get_all_daily_usage():
    return dict(daily_token_usage)


def reset_daily_usage():
    """重置当日token使用计数（通常在每日5点重启时自动完成）"""
    daily_token_usage.clear()
    print("每日token使用计数已重置")


# === token 系统结束 ===


async def chat_with_persona(user_input, group_id=None, member_id=None, member_name=None):
    proxies = PROXY_CONFIG if PROXY_CONFIG else None
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT ai_model_name, ai_prompt_content, temperature, url
                        FROM ai_config
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, (group_id,))
                db_config = cursor.fetchone()

                if db_config:
                    ai_model_name, ai_prompt_content, temperature, ai_url = db_config
                    temperature = float(temperature)
                else:
                    ai_model_name = "deepseek-v4-flash" if group_id in DEEPSEEK_GROUPS else "deepseek-v4-flash"
                    ai_prompt_content = ai_prompt_content_0
                    temperature = 0.2
                    ai_url = "deepseek"

    except pymysql.MySQLError as e:
        print(f"数据库错误: {e}")
        ai_model_name = "deepseek-v4-flash"
        ai_prompt_content = ai_prompt_content_0
        temperature = 0.2
        ai_url = "deepseeek"
        proxies = None

    # 获取当前用户印象
    current_impression = await get_user_impression(member_id, group_id) if member_id else "暂无印象噢!请多多和我聊天吧`"

    # 修改系统提示，加入用户印象
    modified_prompt = f"{ai_prompt_content}\n\n当前用户印象: {current_impression}(请根据印象分数来决定回复的语气的态度)"

    history = chat_histories.get(group_id, [])
    messages = [
        {"role": "system", "content": modified_prompt},  # 使用修改后的提示
        *history[-20:],
        {"role": "user", "content": user_input}
    ]

    try:
        if ai_url not in clients:
            http_client = httpx.AsyncClient(proxies=proxies) if proxies else httpx.AsyncClient()
            clients[ai_url] = {
                "instance": AsyncOpenAI(
                    base_url=ai_url,
                    http_client=http_client
                ),
                "http_client": http_client
            }

        client = clients[ai_url]["instance"]
        response = await client.chat.completions.create(
            model=ai_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=8000
        )
        bot_response = response.choices[0].message.content

        # 更新token使用量
        await update_daily_token_usage(group_id, member_id, user_input, bot_response)

    except Exception as e:
        print(f"API调用错误: {e}")
        bot_response = f"抱歉，请稍后再试qwq\n{str(e)}"

    # 更新聊天历史
    history.extend([
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": bot_response}
    ])
    chat_histories[group_id] = history[-20:]  # 只保留最近10条消息

    # 更新用户印象
    if member_id:
        try:
            message_counters[group_id][member_id] += 1

            # 每5条消息更新一次印象
            if message_counters[group_id][member_id] >= 3:
                new_impression = await generate_impression_update(
                    current_impression,
                    history[-3:]
                )
                await update_user_impression(member_id, group_id, new_impression)

                message_counters[group_id][member_id] = 0

        except Exception as e:
            print(f"更新用户印象失败: {e}")

    return bot_response


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb查询token")]
    )
)
async def query_my_token(app: Ariadne, group: Group, member: Member):
    try:
        usage = get_daily_token_usage(group.id, member.id)
        response = f"今日消耗的token数:\n{usage}"
        message = MessageChain(response)
        await app.send_message(group, message)
    except Exception as e:
        await app.send_message(
            group,
            MessageChain(f"查询token失败: {str(e)}"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb查询全群token")]
    )
)
async def query_all_token(app: Ariadne, group: Group, member: Member):
    """管理员查询所有用户token使用情况"""
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有授权用户可查询哦～"))

    try:
        all_usage = get_all_daily_usage()
        if not all_usage:
            return await app.send_message(group, MessageChain("今日尚无"))

        response = "今日使用情况:\n"
        for user_key, count in all_usage.items():
            parts = user_key.split('_')
            if len(parts) == 2:
                response += f" {parts[1]} 在某群用了: {count} tokens\n"

        await app.send_message(group, MessageChain(response))
    except Exception as e:
        await app.send_message(group, MessageChain(f"查询token失败: {str(e)}"))


# """处理token查询命令"""
# if command == "!token":
#     usage = get_daily_token_usage(group_id, member_id)
#     return f"您今日已消耗 {usage} tokens"
#
# elif command == "!tokenall" and is_admin(member_id):  # 假设有is_admin函数检查管理员权限
#     all_usage = get_all_daily_usage()
#     if not all_usage:
#         return "今日尚无token使用记录"
#
#     response = "今日token使用情况:\n"
#     for user_key, count in all_usage.items():
#         # 解析user_key为group_id和member_id
#         parts = user_key.split('_')
#         if len(parts) == 2:
#             response += f"用户 {parts[1]} (群 {parts[0]}): {count} tokens\n"
#
#     return response
#
# return None

@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb查询好感排行")]
    )
)
async def query_group_token_ranking(app: Ariadne, group: Group, member: Member):
    try:
        all_usage = get_all_daily_usage()
        if not all_usage:
            return await app.send_message(group, MessageChain("本群今日尚无好感度变更"))

        # 筛选当前群组的token使用数据
        group_usage = {}
        for user_key, count in all_usage.items():
            parts = user_key.split('_')
            if len(parts) == 2 and int(parts[0]) == group.id:
                user_id = int(parts[1])
                group_usage[user_id] = count

        if not group_usage:
            return await app.send_message(group, MessageChain("本群今日尚无好感度变更"))

        sorted_usage = sorted(group_usage.items(), key=lambda x: x[1], reverse=True)

        # 获取用户昵称
        response = "今日好感度排行:\n"
        for i, (user_id, count) in enumerate(sorted_usage[:10], 1):  # 显示前10名
            try:
                user_info = await app.get_member(group, user_id)
                user_name = user_info.name
            except:
                user_name = f"用户{user_id}"

            response += f"{i}. {user_name}: {count} \n"

        # 添加最高使用者的特殊提示
        top_user_id, top_count = sorted_usage[0]
        try:
            top_user_info = await app.get_member(group, top_user_id)
            top_user_name = top_user_info.name
        except:
            top_user_name = f"用户{top_user_id}"

        response += f"\n🏆 今日最高好感度: {top_user_name} ({top_count} )"

        await app.send_message(group, MessageChain(response))

    except Exception as e:
        await app.send_message(group, MessageChain(f"查询排行失败: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def voice(app: Ariadne, group: Group, member: Member, message: MessageChain):
    if not re.search(r"@" + BOT_SELF_ID, message.display.strip()):
        return

    if member.id not in ADMIN_USER_IDS and member.id not in PRIVILEGED_USER_IDS:
        current_time = time.time()
        last_used = cooldown_records.get(member.id, 0)

        # 从数据库获取群聊冷却时间设置
        cooldown_time = await get_group_cooldown(group.id)

        # 为特定ID设置不同的冷却时间（优先级高于群设置）
        if str(member.id) in SPECIAL_COOLDOWN_USERS:
            cooldown_time = SPECIAL_COOLDOWN_USERS[str(member.id)]

        if current_time - last_used < cooldown_time:
            remain = cooldown_time - int(current_time - last_used)
            return await app.send_message(
                group,
                MessageChain(f"布咿~")
            )

        cooldown_records[member.id] = current_time

    try:

        user_input = message.display.replace('@' + BOT_SELF_ID, '').strip()
        audio_bytes = await silkcoder.async_encode(VOICE_FILE_PATH, ios_adaptive=True)
        if not user_input:
            return await app.send_message(group, MessageChain(Voice(data_bytes=audio_bytes)))

        await record_group_message(group.id, member.id, member.name, user_input)

        time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        user_input = (
                         f"时间:{time_now}id为:") + str(
            member.id) + " 昵称为:" + member.name + "对你说：(" + user_input + ")"

        if is_agent_mode(group.id):
            response_text, agent_images = await run_agent_chat(
                user_input,
                group_id=group.id,
                member_id=member.id,
                member_name=member.name
            )
        else:
            response_text = await chat_with_persona(
                user_input,
                group_id=group.id,
                member_id=member.id,
                member_name=member.name
            )
            agent_images = []
        response_text = re.sub(
            r'<think>.*?</think>',
            '',
            response_text,
            flags=re.DOTALL
        )
        response_text = response_text.strip()

        # 构造回复消息链
        msg_elements = [Plain(" " + response_text)]
        for img_path in agent_images:
            if img_path and Path(img_path).exists():
                msg_elements.append(Image(path=img_path))
        await app.send_message(group, MessageChain(msg_elements))

    except Exception as e:
        await app.send_message(group, MessageChain(f"布咿~出错了: {str(e)}"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        decorators=[DetectPrefix("yb清除记忆")]
    )
)
async def install(app: Ariadne, group: Group):
    reset_memory(group.id)
    await app.send_message(group, MessageChain("....."))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb创建ai")]))
async def create_ai(app: Ariadne, group: Group, member: Member):
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有他们可修改哦～"))

    await app.send_message(group, MessageChain("输入ai模型"))

    @Waiter.create_using_function([GroupMessage])
    async def setu_tag_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(setu_tag_waiter, timeout=30)
    except asyncio.TimeoutError:
        await app.send_message(group, MessageChain("超时录入!"))
        return

    content = ret_msg.display.strip()
    ai_prompt_content = config['ai_prompt_content']
    temperature = 0.9

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """INSERT INTO ai_config
                        (qq_user_id, qq_group_name, qq_group_id, ai_model_name, ai_prompt_content, temperature)
                        VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (
                    member.id,
                    member.name,
                    group.id,
                    content,
                    ai_prompt_content,
                    temperature
                ))
                conn.commit()
                await app.send_message(group, MessageChain("创建成功!"))

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
        if 'conn' in locals():
            conn.rollback()
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb修改模型")]))
async def update_ai_model(app: Ariadne, group: Group, member: Member):
    # 权限验证
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有他们可修改哦～"))

    await app.send_message(group, MessageChain("请输入新的AI模型名称"))

    @Waiter.create_using_function([GroupMessage])
    async def model_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(model_waiter, timeout=30)
    except asyncio.TimeoutError:
        return await app.send_message(group, MessageChain("超时录入!"))

    new_model = ret_msg.display.strip()
    if not new_model:
        return await app.send_message(group, MessageChain("模型名称不能为空"))

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """UPDATE ai_config
                        SET ai_model_name = %s
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, (new_model, group.id))
                conn.commit()
                await app.send_message(group, MessageChain(f"模型已更新为: {new_model}"))
                reset_memory(group.id)

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
        conn.rollback()
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb修改人格")]))
async def update_ai_prompt(app: Ariadne, group: Group, member: Member):
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有授权用户可修改哦～"))

    await app.send_message(group, MessageChain("请输入新人格设定(用'单引号'包裹内容)"))

    @Waiter.create_using_function([GroupMessage])
    async def prompt_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(prompt_waiter, timeout=30)
    except asyncio.TimeoutError:
        return await app.send_message(group, MessageChain("超时录入!"))

    content = ret_msg.display.strip()
    match = re.match(r"((?<!\\)'(.*?)(?<!\\)')", content, re.DOTALL)
    if not match:
        return await app.send_message(group, MessageChain("格式错误，请用英文单引号包裹设定内容"))

    new_prompt = match.group(1)
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """UPDATE ai_config
                        SET ai_prompt_content = %s
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, (new_prompt, group.id))
                conn.commit()
                await app.send_message(group, MessageChain(f"人格设定已更新"))
                reset_memory(group.id)

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
        conn.rollback()
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb查询ai")]))
async def query_ai_config(app: Ariadne, group: Group, member: Member):
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT ai_model_name, ai_prompt_content, temperature, url
                        FROM ai_config
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, group.id)
                result = cursor.fetchone()

                if not result:
                    return await app.send_message(group, MessageChain("当前群组尚未创建AI配置"))

                model, prompt, temp, url = result
                msg_list = [
                    "模型:\n", str(model),
                    "温度:\n", str(temp),
                    "url:\n", str(url)
                ]
                fwd_nodeList = [
                    ForwardNode(
                        target=member,
                        time=datetime.now(),
                        message=MessageChain("AI配置"),
                    )
                ]
                member_list = await app.get_member_list(group)
                random_members = random.choices(member_list, k=len(msg_list))
                for msg, random_member in zip(msg_list, random_members):
                    fwd_nodeList.append(
                        ForwardNode(
                            target=random_member,
                            time=datetime.now(),
                            message=MessageChain(msg),
                        )
                    )
                message = MessageChain(Forward(nodeList=fwd_nodeList))
                await app.send_message(group, message)

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb修改温度")]))
async def update_ai_temp(app: Ariadne, group: Group, member: Member):
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有授权用户可修改哦～"))

    await app.send_message(group, MessageChain("请输入新温度值(0-2之间的小数)"))

    @Waiter.create_using_function([GroupMessage])
    async def temp_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(temp_waiter, timeout=30)
    except asyncio.TimeoutError:
        return await app.send_message(group, MessageChain("超时录入!"))

    # 温度值验证
    try:
        new_temp = float(ret_msg.display.strip())
        if not 0 <= new_temp <= 2:
            raise ValueError
    except ValueError:
        return await app.send_message(group, MessageChain("温度值必须为0-2之间的数字"))

    # 数据库更新
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """UPDATE ai_config
                        SET temperature = %s
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, (new_temp, group.id))
                conn.commit()
                await app.send_message(group, MessageChain(f"温度值已更新为: {new_temp}"))
                reset_memory(group.id)

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
        conn.rollback()
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb修改url")]))
async def update_ai_model(app: Ariadne, group: Group, member: Member):
    # 权限验证
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有他们可修改哦～"))

    await app.send_message(group, MessageChain("请输入"))

    @Waiter.create_using_function([GroupMessage])
    async def model_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(model_waiter, timeout=30)
    except asyncio.TimeoutError:
        return await app.send_message(group, MessageChain("超时录入!"))

    new_url = ret_msg.display.strip()
    if not new_url:
        return await app.send_message(group, MessageChain("不能为空"))

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """UPDATE ai_config
                        SET url = %s
                        WHERE qq_group_id = %s"""
                cursor.execute(sql, (new_url, group.id))
                conn.commit()
                await app.send_message(group, MessageChain(f"已更新为: {new_url}"))

    except pymysql.MySQLError as e:
        await app.send_message(group, MessageChain(f"数据库错误: {e.args[0]}"))
        conn.rollback()
    except Exception as e:
        await app.send_message(group, MessageChain(f"系统错误: {str(e)}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb设置冷却时间")]))
async def set_cooldown(app: Ariadne, group: Group, member: Member):
    # 权限验证
    if member.id not in ALLOWED_USERS:
        return await app.send_message(group, MessageChain("只有授权用户可修改哦～"))

    await app.send_message(group, MessageChain("请输入冷却时间（秒）"))

    @Waiter.create_using_function([GroupMessage])
    async def cooldown_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(cooldown_waiter, timeout=30)
    except asyncio.TimeoutError:
        return await app.send_message(group, MessageChain("超时录入!"))

    try:
        cooldown_time = int(ret_msg.display.strip())
        if cooldown_time < 0:
            return await app.send_message(group, MessageChain("冷却时间不能为负数"))
    except ValueError:
        return await app.send_message(group, MessageChain("请输入有效的数字"))

    success, error_msg = await set_group_cooldown(group.id, cooldown_time)
    if success:
        await app.send_message(group, MessageChain(f"冷却时间已设置为: {cooldown_time} 秒"))
    else:
        await app.send_message(group, MessageChain(f"设置冷却时间失败: {error_msg}"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb查询冷却时间")]))
async def query_cooldown(app: Ariadne, group: Group, member: Member):
    cooldown_time = await get_group_cooldown(group.id)
    await app.send_message(group, MessageChain(f"当前冷却时间: {cooldown_time} 秒"))


async def init_group_messages_table():
    """初始化群聊消息存储表"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """
                CREATE TABLE IF NOT EXISTS group_chat_messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    group_id BIGINT NOT NULL,
                    member_id BIGINT NOT NULL,
                    member_name VARCHAR(255),
                    message_text TEXT,
                    message_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_group_time (group_id, message_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
                cursor.execute(sql)
                conn.commit()
    except pymysql.MySQLError as e:
        print(f"初始化群聊消息表失败: {e}")


async def record_group_message(group_id: int, member_id: int, member_name: str, message_text: str):
    """记录群聊消息到数据库"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """INSERT INTO group_chat_messages 
                         (group_id, member_id, member_name, message_text) 
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (group_id, member_id, member_name, message_text))
                conn.commit()
    except pymysql.MySQLError as e:
        print(f"记录群聊消息失败: {e}")


async def get_daily_chat_messages(group_id: int) -> list:
    """获取指定群今日所有聊天消息"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """SELECT member_name, message_text, message_time 
                         FROM group_chat_messages 
                         WHERE group_id = %s 
                         AND DATE(message_time) = CURDATE()
                         ORDER BY message_time ASC"""
                cursor.execute(sql, (group_id,))
                results = cursor.fetchall()
                return results
    except pymysql.MySQLError as e:
        print(f"获取今日聊天消息失败: {e}")
        return []


async def summarize_chat_with_ai(chat_messages: list, group_id: int) -> str:
    """使用AI总结群聊内容"""
    if not chat_messages:
        return "今日群聊暂无消息~"

    try:
        client = clients["deepseek"]["instance"]

        chat_text = "\n".join([f"[{time.strftime('%H:%M')}] {name}: {msg}"
                               for name, msg, time in chat_messages])

        messages = [
            {
                "role": "system",
                "content": config['summarize_chat_with_ai']
            },
            {
                "role": "user",
                "content": f"请总结以下今日群聊内容：\n\n{chat_text}"
            }
        ]

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI总结失败: {e}")
        return "今日群聊总结生成失败，请稍后再试qwq"


async def clear_old_messages(days: int = 7):
    """清理指定天数之前的消息"""
    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = """DELETE FROM group_chat_messages 
                         WHERE message_time < DATE_SUB(NOW(), INTERVAL %s DAY)"""
                cursor.execute(sql, (days,))
                conn.commit()
                print(f"已清理 {cursor.rowcount} 条旧消息")
    except pymysql.MySQLError as e:
        print(f"清理旧消息失败: {e}")


@channel.use(SchedulerSchema(timers.crontabify("0 23 * * *")))
async def daily_group_summary(app: Ariadne):
    """每日定时总结所有开启总结功能的群聊"""
    await init_group_messages_table()

    try:
        with pymysql.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                sql = "SELECT DISTINCT group_id FROM group_chat_messages WHERE DATE(message_time) = CURDATE()"
                cursor.execute(sql)
                groups = cursor.fetchall()
    except pymysql.MySQLError as e:
        print(f"获取群列表失败: {e}")
        return

    for (group_id,) in groups:
        try:
            messages = await get_daily_chat_messages(group_id)

            if len(messages) < 5:
                continue

            summary = await summarize_chat_with_ai(messages, group_id)

            summary_msg = f"📊 今日群聊总结 📊\n\n{summary}"

            await app.send_message(
                Group.lookup_identify(str(group_id)),
                MessageChain(summary_msg)
            )

            await asyncio.sleep(3)

        except Exception as e:
            print(f"处理群 {group_id} 总结时出错: {e}")
            continue

    await clear_old_messages(7)