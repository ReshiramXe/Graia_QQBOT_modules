# 接入蘑菇的宝音网站接口


import os
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import requests
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Voice
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema
from graia.ariadne.message.parser.base import MatchContent
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
import graiax.silkcoder as silkcoder
from graia.broadcast.interrupt import InterruptControl
from graia.saya import Saya

saya = Saya.current()
channel = Channel.current()
inc = InterruptControl(saya.broadcast)


def load_config():
    config_path = Path(__file__).parent / 'config' / 'kinoko.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


config = load_config()
BASE_DOWNLOAD_PATH = config['download_paths']['base']
BASE_DOWNLOAD_PATH2 = config['download_paths']['sjmusic3']
api_key = config['api']['kinoko']['api_key']
BASE_URL = config['api']['kinoko'].get('base_url', 'http://your-music-api-domain.com')


def search_music(keyword):
    url = f'{BASE_URL}/search/ajax_search_music?text={keyword}'
    response = requests.get(url)
    response.encoding = 'utf-8'
    data = response.json()
    music_id = [item['id'] for item in data][0]

    url2 = f'{BASE_URL}/open/get_music_info?api_key={api_key}&music_id={music_id}'
    response = requests.get(url2)
    response.encoding = 'utf-8'
    data2 = response.json()
    music_src = data2['data']['src']
    filename = f'{keyword}.mp3'

    full_path = os.path.join(BASE_DOWNLOAD_PATH, filename)
    response = requests.get(music_src)
    response.encoding = 'utf-8'

    if response.status_code == 200:
        with open(full_path, 'wb') as file:
            file.write(response.content)

    else:
        return None
    return full_path


def get_random_music():
    try:
        url = f'{BASE_URL}/open/get_random_music_id?api_key={api_key}&sound=false&user_submission=true'
        response = requests.get(url)
        response.encoding = 'utf-8'
        data = response.json()
        music_id = data.get('music_id')

        if not music_id:
            return None

        url2 = f'{BASE_URL}/open/get_music_info?api_key={api_key}&music_id={music_id}'
        response = requests.get(url2)
        response.encoding = 'utf-8'
        data2 = response.json()

        if not data2.get('data') or not data2['data'].get('src'):
            return None

        music_src = data2['data']['src']
        filename = os.path.basename(music_src)

        full_path2 = os.path.join(BASE_DOWNLOAD_PATH2, filename)
        response = requests.get(music_src)

        if response.status_code == 200:
            with open(full_path2, 'wb') as file:
                file.write(response.content)
            return full_path2
        else:
            return None
    except Exception as e:
        print(f"获取随机音乐失败: {e}")
        return None


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def handle_message(app: Ariadne, group: Group, message: MessageChain):
    TRIGGER_KEYWORD = "来点宝音"
    message_str = str(message)

    if message_str.startswith(TRIGGER_KEYWORD):
        data = message_str.replace(TRIGGER_KEYWORD, "").strip()
        full_path = search_music(data)
        if full_path:
            audio_bytes = await silkcoder.async_encode(full_path, ios_adaptive=True)
            await app.send_message(group, MessageChain(Voice(data_bytes=audio_bytes)))
        else:
            await app.send_message(group, MessageChain("没有找到音乐qwq ，可能是名字不对!"))


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("随机宝音")]))
async def random_kinoko(app: Ariadne, group: Group):
    full_path2 = get_random_music()

    if full_path2 and os.path.exists(full_path2):
        audio_bytes = await silkcoder.async_encode(full_path2, ios_adaptive=True)
        await app.send_message(group, MessageChain(Voice(data_bytes=audio_bytes)))
    else:
        print("获取失败qwq")