# 每日日期提醒的管理


import asyncio
import yaml
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema
from time import sleep
from graia.ariadne.model import Member
import datetime
import pymysql

channel = Channel.current()

def load_config():
    config_path = Path(__file__).parent / 'config' / 'datedel.yaml'
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
GROUP_IDS = config.get('groups', [])


def get_latest_messages():
    conn = pymysql.connect(**DB_CONFIG)

    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name, date FROM qqbotdate")
        data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return data


def delete_data(name):
    conn = pymysql.connect(**DB_CONFIG)

    cursor = conn.cursor()

    sql = "DELETE FROM qqbotdate WHERE name = %s"
    try:
        cursor.execute(sql, (name,))
        conn.commit()
        print("数据删除成功")
    except Exception as e:
        conn.rollback()
        print("数据删除失败:", str(e))
    finally:
        cursor.close()
        conn.close()


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def setu_get_date(app: Ariadne, group: Group, member: Member, message: MessageChain):
    if group.id not in GROUP_IDS:
        return

    if message.display == "yb完整日期":
        data = get_latest_messages()
        current_year = datetime.datetime.now().year
        converted_data = [(item[0], datetime.datetime.strptime(f"{current_year}{item[1]}", "%Y%m%d")) for item in data]
        sorted_data = sorted(converted_data, key=lambda x: x[1])
        result = "\n".join(f"{x[0]} - {str(x[1].month).zfill(2)}-{str(x[1].day).zfill(2)}" for x in sorted_data)
        msg = await app.send_message(group, MessageChain([Plain(result)]))
        await asyncio.sleep(40)
        await app.recall_message(msg)


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def setu_delete_date(app: Ariadne, group: Group, message: MessageChain):
    if group.id not in GROUP_IDS:
        return

    TRIGGER_KEYWORD = "yb删除日期"
    message_str = str(message)

    if message_str.startswith(TRIGGER_KEYWORD):
        message_text = " ".join(message_str.split())
        try:
            name_to_delete = message_text.split()[1]
            delete_data(name_to_delete)
            await app.send_message(group, MessageChain([Plain("删除成功")]))
        except IndexError:
            await app.send_message(group, MessageChain([Plain("请提供要删除的名称\n例如：yb删除日期 白白")]))
