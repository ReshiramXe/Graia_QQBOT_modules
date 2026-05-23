# 每日日期提醒的日期录入


import yaml
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema
import pymysql


channel = Channel.current()


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config' / 'date_input.yaml'
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
GROUP_KEYWORDS = config.get('group_keywords', {})


def insert_data(name, date):
    # 连接到MySQL数据库
    conn = pymysql.connect(**DB_CONFIG)

    # 创建游标
    cursor = conn.cursor()

    # 插入数据
    sql = "INSERT INTO qqbotdate (name, date) VALUES (%s, %s)"
    values = (name, date)

    try:
        cursor.execute(sql, values)
        conn.commit()
        print("数据插入成功")
    except Exception as e:
        conn.rollback()
        print("数据插入失败:", str(e))

    # 关闭游标和数据库连接
    cursor.close()
    conn.close()


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def setu(app: Ariadne, group: Group, message: MessageChain):
    keyword = GROUP_KEYWORDS.get(str(group.id))
    if keyword and str(message).startswith(keyword):
        # 预处理消息中的空格
        message_text = " ".join(str(message).split())
        data = message_text.split(" ", 2)
        if len(data) == 3:
            name = data[1]
            date = data[2]
            if len(date) == 4 and date.isdigit():
                month = int(date[0:2])
                day = int(date[2:4])
                if month == 2:
                    if day in range(1, 29):
                        insert_data(name, date)
                        await app.send_message(
                            group,
                            MessageChain([Plain("输入成功")]),
                        )
                    else:
                        await app.send_message(
                            group,
                            MessageChain([Plain("日期不符合现实")]),
                        )
                elif month in [1, 3, 5, 7, 8, 10, 12]:
                    if day in range(1, 32):
                        insert_data(name, date)
                        await app.send_message(
                            group,
                            MessageChain([Plain("输入成功")]),
                        )
                    else:
                        await app.send_message(
                            group,
                            MessageChain([Plain("日期不符合现实")]),
                        )
                elif month in [4, 6, 9, 11]:
                    if day in range(1, 31):
                        insert_data(name, date)
                        await app.send_message(
                            group,
                            MessageChain([Plain("输入成功")]),
                        )
                    else:
                        await app.send_message(
                            group,
                            MessageChain([Plain("日期不符合现实")]),
                        )
                else:
                    await app.send_message(
                        group,
                        MessageChain([Plain("日期不符合现实")]),
                    )
            else:
                await app.send_message(
                    group,
                    MessageChain([Plain("格式错误qw 栗子：\n“yb加入日期 白白 0229”")]),
                )
        else:
            await app.send_message(
                group,
                MessageChain([Plain("格式错误qw 栗子：\n“yb加入日期 白白 0229”")]),
            )
