# 功能菜单


import asyncio
import yaml
import pymysql
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema

channel = Channel.current()

def load_config():
    config_path = Path(__file__).parent / 'config' / 'menu.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
DB_CONFIG = config.get('database', {
    'host': '',
    'user': '',
    'passwd': '',
    'port': 3306,
    'db': '',
    'charset': 'utf8'
})

@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def setu(app: Ariadne, group: Group, message: MessageChain):
    if message.display == "叶布功能w":
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        sql = "SELECT content FROM menu"
        cursor.execute(sql)
        rows = cursor.fetchall()


        if rows:
            MENU_ITEMS = [row[0] for row in rows]
            formatted_menu_text = '\n\n'.join(MENU_ITEMS)
        else:
            formatted_menu_text = "菜单为空"


        msg = await app.send_message(
            group,
            MessageChain([Plain(formatted_menu_text)]),
        )
        await asyncio.sleep(40)


        await app.recall_message(msg)

        cursor.close()
        conn.close()
