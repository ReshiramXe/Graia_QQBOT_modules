# 每日日期提醒的删除日期


import yaml
from pathlib import Path
import asyncio
import pymysql
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group, Member
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import MatchContent
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Union
from creart import create
from graia.ariadne.message.element import Image, Plain
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

saya = Saya.current()
channel = Channel.current()
inc = create(InterruptControl)

def load_config():
    config_path = Path(__file__).parent / 'config' / 'date_deleter.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


config = load_config()
DB_CONFIG = config.get('database', {
    'host': '',
    'user': '',
    'passwd': '',
    'port': 3306,
    'db': '',
    'charset': 'utf8mb4'
})


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb删除定时")]))
async def delete_message(app: Ariadne, group: Group, member: Member):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    sql = "SELECT id, message, time_created FROM dallytime WHERE member_id = %s AND group_id = %s"
    cursor.execute(sql, (member.id, group.id))
    results = cursor.fetchall()

    if results:
        messages = "\n".join(f"ID: {row[0]} | {datetime.strftime(row[2], '%H:%M')} | {row[1]}" for row in results)
        await app.send_message(group, MessageChain(f"以下是您的所有定时uwu:\n{messages}\n输入要删除的ID："))

        @Waiter.create_using_function([GroupMessage])
        async def setu_tag_waiter(g: Group, m: Member, msg: MessageChain):
            if group.id == g.id and member.id == m.id:
                return msg

        try:
            ret_msg: MessageChain = await inc.wait(setu_tag_waiter, timeout=20)
        except asyncio.TimeoutError:
            await app.send_message(group, MessageChain("超时录入!"))
            return

        delete_id = ret_msg.display.strip()

        delete_sql = "DELETE FROM dallytime WHERE id = %s AND member_id = %s"
        cursor.execute(delete_sql, (delete_id, member.id))
        conn.commit()
        await app.send_message(group, MessageChain("删除成功!"))
    else:
        await app.send_message(group, MessageChain("没有找到相关消息."))

    cursor.close()
    conn.close()


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("yb定时查询")]))
async def query_message(app: Ariadne, group: Group, member: Member):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    sql = "SELECT id, message, time_created FROM dallytime WHERE group_id = %s"
    cursor.execute(sql, (group.id,))
    results = cursor.fetchall()

    if results:
        messages = "\n".join(f"ID: {row[0]} | {datetime.strftime(row[2], '%H:%M')} | {row[1]}" for row in results)
        await app.send_message(group, MessageChain(f"本群所有定时:\n{messages}"))
    else:
        await app.send_message(group, MessageChain("没有找到相关消息."))
