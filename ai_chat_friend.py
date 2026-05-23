import asyncio
import re
import time
import yaml
import pymysql
import graiax.silkcoder as silkcoder
from openai import AsyncOpenAI
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import FriendMessage
from graia.ariadne.message.element import Voice, Plain
from graia.ariadne.model import Friend
from graia.ariadne.message.chain import MessageChain
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import DetectPrefix, MatchContent
from graia.broadcast.interrupt import InterruptControl
from creart import create

channel = Channel.current()
saya = Saya.current()
chat_histories = {}
cooldown_records = {}
model_settings = {}
inc = create(InterruptControl)

def load_config():
    config_path = Path(__file__).parent / 'config' / 'ai_bot_friend.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
ai_prompt_content_default = config.get('ai_prompt_content_default', '')
ALLOWED_USERS = set(config.get('allowed_users', []))
DB_CONFIG = config.get('database', {
    'host': '',
    'user': '',
    'passwd': '',
    'port': 3306,
    'db': '',
    'charset': 'utf8mb4'
})

# API配置
API_CONFIG = config.get('api', {}).get('deepseek', {})
DEFAULT_MODEL = API_CONFIG.get('model', 'deepseek-chat')

# 对话配置
CONV_CONFIG = config.get('conversation', {})
MAX_HISTORY = CONV_CONFIG.get('max_history', 20)
CONTEXT_LENGTH = CONV_CONFIG.get('context_length', 5)
DEFAULT_TEMPERATURE = CONV_CONFIG.get('temperature', 0.8)
FREQUENCY_PENALTY = CONV_CONFIG.get('frequency_penalty', 0.5)
MAX_TOKENS = CONV_CONFIG.get('max_tokens', 4000)

# 冷却配置
COOLDOWN_CONFIG = config.get('cooldown', {})
COOLDOWN_ENABLED = COOLDOWN_CONFIG.get('enabled', True)
COOLDOWN_SECONDS = COOLDOWN_CONFIG.get('normal_user_seconds', 15)
VOICE_FILE = COOLDOWN_CONFIG.get('voice_file', 'data/voices/default.mp3')

# 管理员ID（不受冷却限制）
ADMIN_USER_ID = config.get('admin_user_id', 0)

aclient = AsyncOpenAI(
    api_key=API_CONFIG.get('api_key', ''),
    base_url=API_CONFIG.get('base_url', '')
)


# 清除群聊记忆
def reset_memory(group_id):
    chat_histories.pop(group_id, None)


async def install(app: Ariadne, friend: Friend, message: MessageChain):
    reset_memory(friend.id)
    await app.send_message(friend, MessageChain("......"))


# 核心对话函数
async def chat_with_persona(user_input, group_id=None):
    try:
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                sql = """SELECT ai_model_name, ai_prompt_content, temperature
                         FROM ai_config_2
                         WHERE qq_user_id = %s"""
                cursor.execute(sql, group_id)
                db_config = cursor.fetchone()

                if db_config:
                    ai_model_name = DEFAULT_MODEL
                    ai_prompt_content = ai_prompt_content_default
                    temperature = DEFAULT_TEMPERATURE
                else:
                    ai_model_name = DEFAULT_MODEL
                    ai_prompt_content = ai_prompt_content_default
                    temperature = DEFAULT_TEMPERATURE
        finally:
            conn.close()
    except pymysql.MySQLError:
        ai_model_name = DEFAULT_MODEL
        ai_prompt_content = ai_prompt_content_default
        temperature = DEFAULT_TEMPERATURE

    history = chat_histories.get(group_id, [])
    messages = [
        {"role": "system", "content": ai_prompt_content},
        *history[-CONTEXT_LENGTH:],
        {"role": "user", "content": user_input}
    ]

    try:
        response = await aclient.chat.completions.create(
            model=ai_model_name,
            messages=messages,
            temperature=temperature,
            frequency_penalty=FREQUENCY_PENALTY,
            max_tokens=MAX_TOKENS
        )
        bot_response = response.choices[0].message.content
    except Exception as e:
        bot_response = f"出错了: {str(e)}"

    # 更新历史记录
    history.extend([
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": bot_response}
    ])
    chat_histories[group_id] = history[-MAX_HISTORY:]
    return bot_response


# 消息监听
@channel.use(ListenerSchema(listening_events=[FriendMessage]))
async def voice(app: Ariadne, friend: Friend, message: MessageChain):
    if not message.display or not message.display.strip():
        return

    # 冷却机制
    if COOLDOWN_ENABLED and friend.id != ADMIN_USER_ID:
        current_time = time.time()
        last_used = cooldown_records.get(friend.id, 0)
        if current_time - last_used < COOLDOWN_SECONDS:
            remain = COOLDOWN_SECONDS - int(current_time - last_used)
            return await app.send_message(
                friend,
                MessageChain(f"布咿~太频繁啦！请{remain}秒后再问哦~")
            )
        cooldown_records[friend.id] = current_time

    try:
        user_input = message.display.replace('/y', '').strip()
        audio_bytes = await silkcoder.async_encode(VOICE_FILE, ios_adaptive=True)

        if not user_input:
            return await app.send_message(friend, MessageChain(Voice(data_bytes=audio_bytes)))

        user_input = (
            f"id为:{friend.id} 昵称为:{friend.nickname}的人对你说：({user_input})")
        response_text = await chat_with_persona(user_input, group_id=friend.id)

        # 去除 <think> 标签
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()

        await app.send_message(friend, MessageChain(Plain(response_text)))
    except Exception as e:
        await app.send_message(friend, MessageChain(f"布咿~出错了: {str(e)}"))