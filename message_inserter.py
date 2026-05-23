# 消息插入


import asyncio
import yaml
import pymysql
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group, Member
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import MatchContent
from datetime import datetime
from typing import Union
from creart import create
from graia.ariadne.message.element import Image, Plain
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter
from graia.scheduler.saya import SchedulerSchema
from graia.scheduler import timers

saya = Saya.current()
channel = Channel.current()
inc = create(InterruptControl)

def load_config():
    config_path = Path(__file__).parent / 'config' / 'insert_message.yaml'
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


@channel.use(SchedulerSchema(timers.crontabify("*/1 * * * *")))  # 每分钟检查一次
async def check_scheduled_messages(app: Ariadne):
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    nowtime = datetime.now().strftime("%H:%M")

    try:
        # 查询所有的定时消息
        sql = f"SELECT group_id, message, DATE_FORMAT(time_created, '%H:%i') AS time FROM dallytime WHERE DATE_FORMAT(time_created, '%H:%i') = '{nowtime}';"

        cursor.execute(sql)
        results = cursor.fetchall()

        if results:
            for row in results:
                group_id, message, time = row  # 确保与查询返回的列数一致
                await app.send_group_message(group_id, MessageChain(message))

    except Exception as e:
        print(f"处理定时消息时发生错误: {str(e)}")  # 记录错误信息

    finally:
        cursor.close()
        conn.close()
