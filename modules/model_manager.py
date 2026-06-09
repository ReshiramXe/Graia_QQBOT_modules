# 模型列表


import os
import yaml
import requests
from pathlib import Path
import asyncio
import os
import re
import pymysql
import random
from datetime import datetime
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Forward, ForwardNode, Image, Voice, Plain
from graia.ariadne.model import Group, Member
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import MatchContent
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter
from creart import create
from modules.config_loader import get_api_keys

channel = Channel.current()
saya = Saya.current()
inc = create(InterruptControl)

def load_config():
    config_path = Path(__file__).parent / 'config' / 'model_list.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

def _get_api_key(provider_name):
    """从YAML统一配置获取API key，环境变量可覆盖"""
    api_keys = get_api_keys()
    env_map = {
        "siliconflow": "SILICONFLOW_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "xiaoai": "XIAOAI_API_KEY",
        "xi_ai": "XI_AI_API_KEY",
        "xai": "XAI_API_KEY",
    }
    env_key = env_map.get(provider_name)
    if env_key:
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val
    return config["api"][provider_name]["api_key"]

def get_model_list(url, headers):
    querystring = {"type": "text", "sub_type": "chat"}
    try:
        response = requests.request("GET", url, headers=headers, params=querystring, timeout=10)
    except RequestException as e:
        print(f"请求发生异常: {e}")
        return None
    if response.status_code == 200:
        try:
            model_data = response.json()
        except json.JSONDecodeError:
            print("无法解析响应为JSON")
            return None
        if 'data' in model_data:
            return model_data['data']
        else:
            print("响应数据中没有找到'data'键")
    else:
        print(f"请求失败，状态码: {response.status_code}")
    return None


def get_siliconflow_models():
    api_config = config['api']['siliconflow']
    url = api_config['url']
    api_key = _get_api_key("siliconflow")
    headers = {"Authorization": f"Bearer {api_key}"}
    return get_model_list(url, headers)


def get_deepseek_models():
    api_config = config['api']['deepseek']
    url = api_config['url']
    api_key = _get_api_key("deepseek")
    headers = {"Authorization": f"Bearer {api_key}"}
    return get_model_list(url, headers)


def get_xiaoai_models():
    api_config = config['api']['xiaoai']
    url = api_config['url']
    api_key = _get_api_key("xiaoai")
    headers = {"Authorization": f"Bearer {api_key}"}
    return get_model_list(url, headers)


def get_xi_ai_models():
    api_config = config['api']['xi_ai']
    url = api_config['url']
    api_key = _get_api_key("xi_ai")
    headers = {"Authorization": f"Bearer {api_key}"}
    return get_model_list(url, headers)


def get_xai_models():
    api_config = config['api']['xai']
    url = api_config['url']
    api_key = _get_api_key("xai")
    headers = {"Authorization": f"Bearer {api_key}"}
    return get_model_list(url, headers)


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb查询模型")]))
async def delete_message(app: Ariadne, group: Group, member: Member):
    await app.send_message(group, MessageChain(f"输入要查询的模型名称ID\n"
                                               f"1.siliconflow\n"
                                               f"2.deepseek\n"
                                               f"3.xiaoai\n"
                                               f"4.xi_ai\n"
                                               f"5.xai\n"))

    @Waiter.create_using_function([GroupMessage])
    async def setu_tag_waiter(g: Group, m: Member, msg: MessageChain):
        if group.id == g.id and member.id == m.id:
            return msg

    try:
        ret_msg: MessageChain = await inc.wait(setu_tag_waiter, timeout=20) 
    except asyncio.TimeoutError:
        await app.send_message(group, MessageChain("超时!"))
        return
    print(ret_msg)

    search_id = ret_msg.display.strip()

    try:
        print(f"环节正常{search_id}")
        if search_id == "1":
            print("环节正常")
            data1 = get_siliconflow_models()
            fwd_nodeList_1 = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("siliconflow模型列表"),
                )
            ]
            member_list = await app.get_member_list(group)
            for data1 in data1:
                msg = data1['id']
                random_member: Member = random.choice(member_list)
                fwd_nodeList_1.append(
                    ForwardNode(
                        target=random_member,
                        time=datetime.now(),
                        message=MessageChain(msg),
                    )
                )
            message = MessageChain(Forward(nodeList=fwd_nodeList_1))
            await app.send_message(group, message)

        elif search_id == "2":
            data2 = get_deepseek_models()

            fwd_nodeList_2 = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("deepseek模型列表"),
                )
            ]
            member_list = await app.get_member_list(group)
            for data2 in data2:
                msg = data2['id']
                random_member: Member = random.choice(member_list)
                fwd_nodeList_2.append(
                    ForwardNode(
                        target=random_member,
                        time=datetime.now(),
                        message=MessageChain(msg),
                    )
                )
            message = MessageChain(Forward(nodeList=fwd_nodeList_2))
            await app.send_message(group, message)

        elif search_id == "3":
            data3 = get_xiaoai_models()
            fwd_nodeList_3 = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("xiaoai模型列表"),
                )
            ]
            member_list = await app.get_member_list(group)
            for data3 in data3:
                msg = data3['id']
                random_member: Member = random.choice(member_list)
                fwd_nodeList_3.append(
                    ForwardNode(
                        target=random_member,
                        time=datetime.now(),
                        message=MessageChain(msg),
                    )
                )
            message = MessageChain(Forward(nodeList=fwd_nodeList_3))
            await app.send_message(group, message)

        elif search_id == "4":
            data4 = get_xi_ai_models()

            fwd_nodeList_4 = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("xi-ai模型列表"),
                )
            ]
            member_list = await app.get_member_list(group)
            for data4 in data4:
                msg = data4['id']
                random_member: Member = random.choice(member_list)
                fwd_nodeList_4.append(
                    ForwardNode(
                        target=random_member,
                        time=datetime.now(),
                        message=MessageChain(msg),
                    )
                )
            message = MessageChain(Forward(nodeList=fwd_nodeList_4))
            await app.send_message(group, message)

        elif search_id == "5":
            data5 = get_xai_models()

            fwd_nodeList_5 = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("xai模型列表"),
                )
            ]
            member_list = await app.get_member_list(group)
            for data5 in data5:
                msg = data5['id']
                random_member: Member = random.choice(member_list)
                fwd_nodeList_5.append(
                    ForwardNode(
                        target=random_member,
                        time=datetime.now(),
                        message=MessageChain(msg),
                    )
                )
            message = MessageChain(Forward(nodeList=fwd_nodeList_5))
            await app.send_message(group, message)

        else:
            await app.send_message(group, MessageChain("没有此模型!"))

    except Exception as e:
        await app.send_message(group, MessageChain(f"错误qwq: {str(e)}"))
