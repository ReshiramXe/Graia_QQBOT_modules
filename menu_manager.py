# 功能加入模块


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
from creart import create
from graia.ariadne.message.element import Image, Plain
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

saya = Saya.current()
channel = Channel.current()
inc = create(InterruptControl)

def load_config():
    config_path = Path(__file__).parent / 'config' / 'menuin.yaml'
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
ADMIN_USER = config.get('admin_user', [])


@channel.use(ListenerSchema(listening_events=[GroupMessage], decorators=[MatchContent("功能加入")]))
async def ero(app: Ariadne, group: Group, member: Member):
    if member.id in ADMIN_USER:
        await app.send_message(group, MessageChain("功能："))

        @Waiter.create_using_function([GroupMessage])
        async def setu_tag_waiter(g: Group, m: Member, msg: MessageChain):
            if group.id == g.id and member.id == m.id:
                return msg

        try:
            ret_msg: MessageChain = await inc.wait(setu_tag_waiter, timeout=10)  # 强烈建议设置超时时间否则将可能会永远等待
        except asyncio.TimeoutError:
            await app.send_message(group, MessageChain("你说话了吗？"))
        else:
            # 提取消息内容
            content = ret_msg.display

            # 连接数据库
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # 插入数据
            sql = "INSERT INTO menu (content) VALUES (%s)"
            values = (content,)

            try:
                cursor.execute(sql, values)
                conn.commit()
                print("数据插入成功")
                await app.send_message(group, MessageChain(Plain("数据插入成功")))
            except Exception as e:
                conn.rollback()
                print("数据插入失败:", str(e))
                await app.send_message(group, MessageChain(Plain("数据插入失败")))
            finally:
                # 关闭游标和数据库连接
                cursor.close()
                conn.close()
    else:
        await app.send_message(group, MessageChain(Plain("你不是叶布主人！")))
