# 生日提示


import sys
import yaml
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.saya import Channel
import datetime
from graia.scheduler import timers
from graia.scheduler.saya import SchedulerSchema

sys.path.append("/root/.pyenv/versions/3.9.7/lib/python3.9/site-packages")
import pymysql

channel = Channel.current()

def load_config():
    config_path = Path(__file__).parent / 'config' / 'datebest.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
group_ids = config.get('groups',[])
DB_CONFIG = config.get('database', {
    'host': '',
    'user': '',
    'passwd': '',
    'port': 3306,
    'db': '',
    'charset': 'utf8'
})


def connect_to_database():
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def query_all_dates(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name, date FROM qqbotdate")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def get_current_date():
    now = datetime.datetime.now()
    return now.year, now.month, now.day


def calculate_current_days(year, month, day):
    month_days = {
        1: 0, 2: 31, 3: 59, 4: 90, 5: 120, 6: 151,
        7: 181, 8: 212, 9: 243, 10: 273, 11: 304, 12: 334
    }
    monthnow = month_days.get(month, 0)
    nowdays = monthnow + day
    return nowdays


def calculate_date_differences(rows, nowdays):
    month_days = {
        1: 0, 2: 31, 3: 59, 4: 90, 5: 120, 6: 151,
        7: 181, 8: 212, 9: 243, 10: 273, 11: 304, 12: 334
    }
    date_differences = []
    for row in rows:
        date = str(row[1])

        front_data = date[:-2]
        last_two_digits = date[-2:]
        days1 = month_days.get(int(front_data), 0)
        days2 = days1 + int(last_two_digits)
        difference = days2 - nowdays

        if difference < 0:
            difference += 365

        date_differences.append((date, difference))

    date_differences.sort(key=lambda x: x[1])
    return date_differences


def create_message_chain(date_differences, rows):
    message_chain = MessageChain([Plain("特别日期：\n")])
    has_special_date = False

    for date, difference in date_differences:
        if difference == 0:
            front_data = date[:-2]
            last_two_digits = date[-2:]
            formatted_date = f"{front_data}-{last_two_digits}"

            birthday_names = [row[0] for row in rows if str(row[1]) == date]
            if birthday_names:
                has_special_date = True
                message_chain += MessageChain([
                    Plain(f"今天是{', '.join(birthday_names)}的生日！\n"),
                ])

    if not has_special_date:
        return None

    return message_chain


def close_database_connection(conn):
    conn.close()


@channel.use(SchedulerSchema(timers.crontabify("0 0 * * *")))
async def recall(app: Ariadne):
    conn = connect_to_database()
    rows = query_all_dates(conn)
    year, month, day = get_current_date()
    nowdays = calculate_current_days(year, month, day)
    date_differences = calculate_date_differences(rows, nowdays)
    message_chain = create_message_chain(date_differences, rows)

    if message_chain:
        for group_id in group_ids:
            await app.send_group_message(group_id, message_chain)

    close_database_connection(conn)
