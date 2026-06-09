# 概率触发的自主回复

import os
import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path

import asyncio
import yaml
from openai import AsyncOpenAI
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema

from modules.shared_memory import get_history, append_history

channel = Channel.current()
last_response_time = defaultdict(float)


# 加载配置
def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config' / 'ai_recall.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# 加载配置
config = load_config()

# 初始化OpenAI客户端 - 从YAML配置加载
client = AsyncOpenAI(
    api_key=config["api"]["api_key"],
    base_url=config["api"]["base_url"]
)

# 配置参数
PROMPT_CONTENT = config['prompt']
TEMPERATURE = config['temperature']
MESSAGE_LIMIT = config['message_limit']
COOLDOWN_TIME = config['cooldown_time']
GROUP_CONFIGS = {int(group_id): prob for group_id, prob in config['group_configs'].items()}
ALLOWED_GROUPS = config['allowed_groups']


def should_trigger(group_id):
    """判断是否应该触发回复"""
    if group_id not in GROUP_CONFIGS:
        return False

    # 检查冷却时间
    current_time = time.time()
    if current_time - last_response_time.get(group_id, 0) < COOLDOWN_TIME:
        return False

    # 检查触发概率
    trigger_probability = GROUP_CONFIGS[group_id]
    return random.random() < trigger_probability


def is_valid_message(message):
    """判断消息是否有效"""
    # 过滤链接和图片
    if re.search(r'https?://\S+|www\.\S+', message.display) or "[图片]" in message.display:
        return False
    # 过滤空消息
    if not message.display.strip():
        return False
    return True


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def handle_message(app: Ariadne, group: Group, message: MessageChain, member: Member):
    # 检查群是否在允许列表中
    if group.id not in ALLOWED_GROUPS:
        return

    # 检查消息是否有效
    if not is_valid_message(message):
        return

    # 格式化消息并写入共享记忆
    current_time = time.strftime("%H:%M")
    formatted_message = f"({current_time}){member.name}: {message.display}"
    append_history(group.id, "user", formatted_message, name=member.name)

    # 获取共享记忆中的近期用户消息
    history = get_history(group.id)
    user_messages = [m["content"] for m in history if m["role"] == "user"]
    recent_messages = user_messages[-MESSAGE_LIMIT:]

    # 当消息数量达到阈值时判断是否触发回复
    if len(recent_messages) >= MESSAGE_LIMIT:
        if should_trigger(group.id):
            combined_message = "\n".join(recent_messages)
            print(f"群 {group.id} 触发自主回复")
            print(combined_message)

            try:
                current_time_str = time.strftime("%H:%M")
                response = await client.chat.completions.create(
                    model=config['api']['model'],
                    messages=[
                        {"role": "system", "content": f"现在的时间:{current_time_str}.{PROMPT_CONTENT}"},
                        {"role": "user", "content": combined_message}
                    ],
                    temperature=TEMPERATURE,
                    stream=False
                )

                ai_response = response.choices[0].message.content.strip()
                # 过滤空回复
                if ai_response:
                    await app.send_message(group, MessageChain(ai_response))
                    # 更新最后回复时间
                    last_response_time[group.id] = time.time()
                    # 记录 bot 自己的回复到共享记忆
                    bot_time = time.strftime("%H:%M")
                    bot_message = f"({bot_time})机叶: {ai_response}"
                    append_history(group.id, "assistant", bot_message, name="机叶")
            except Exception as e:
                print(f"调用OpenAI API时发生错误: {e}")