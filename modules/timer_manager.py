# 定时提醒管理功能


import asyncio
import json
import yaml
import re
from pathlib import Path
import pymysql
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain, At
from graia.ariadne.model import Group, Member
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.message.parser.base import DetectPrefix, MatchContent
from creart import create
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter
from datetime import datetime

saya = Saya.current()
channel = Channel.current()
inc = create(InterruptControl)


def load_config():
    config_path = Path(__file__).parent / 'config' / 'make_date.yaml'
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

ADMIN_GROUP = config.get('admin_group', [])
ALLOWED_GROUPS = config.get('allowed_groups', [])


def get_all_timers(group_id: int = None) -> list:
    """获取指定群或所有群的定时列表"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        if group_id:
            sql = """SELECT id, message, group_id, member_id, time_created 
                     FROM dallytime WHERE group_id = %s ORDER BY time_created"""
            cursor.execute(sql, (group_id,))
        else:
            sql = """SELECT id, message, group_id, member_id, time_created 
                     FROM dallytime ORDER BY group_id, time_created"""
            cursor.execute(sql)

        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except pymysql.MySQLError as e:
        print(f"获取定时列表失败: {e}")
        return []


def delete_timer(timer_id: int) -> bool:
    """删除指定ID的定时"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = "DELETE FROM dallytime WHERE id = %s"
        cursor.execute(sql, (timer_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except pymysql.MySQLError as e:
        print(f"删除定时失败: {e}")
        return False


def update_timer(timer_id: int, message: str = None, time_created: str = None) -> bool:
    """更新指定ID的定时"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        if message and time_created:
            sql = "UPDATE dallytime SET message = %s, time_created = %s WHERE id = %s"
            cursor.execute(sql, (message, time_created, timer_id))
        elif message:
            sql = "UPDATE dallytime SET message = %s WHERE id = %s"
            cursor.execute(sql, (message, timer_id))
        elif time_created:
            sql = "UPDATE dallytime SET time_created = %s WHERE id = %s"
            cursor.execute(sql, (time_created, timer_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except pymysql.MySQLError as e:
        print(f"更新定时失败: {e}")
        return False


def insert_timer(message: str, group_id: int, member_id: int, time_created: str) -> bool:
    """插入新定时"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = "INSERT INTO dallytime (message, group_id, member_id, time_created) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (message, group_id, member_id, time_created))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except pymysql.MySQLError as e:
        print(f"插入定时失败: {e}")
        return False


def format_timer_list(timers: list, show_group: bool = False) -> str:
    """格式化定时列表"""
    if not timers:
        return "暂无定时提醒~"

    result = "📋 定时提醒列表：\n\n"
    current_group = None

    for timer_id, message, group_id, member_id, time_created in timers:
        if show_group and group_id != current_group:
            current_group = group_id
            result += f"━━━ 群 {group_id} ━━━\n"

        time_str = time_created.strftime("%H:%M") if isinstance(time_created, datetime) else str(time_created)
        result += f"[{timer_id}] {time_str} - {message}\n"

    return result.strip()


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[DetectPrefix("yb定时列表")]
))
async def list_timers(app: Ariadne, group: Group, member: Member, message: MessageChain):
    """查看定时列表"""
    keyword = message.display.replace("yb定时列表", "").strip()

    if group.id == ADMIN_GROUP and keyword == "全部":
        timers = get_all_timers()
        result = format_timer_list(timers, show_group=True)
    elif keyword:
        try:
            target_group_id = int(keyword)
            timers = get_all_timers(target_group_id)
            result = format_timer_list(timers)
        except ValueError:
            await app.send_message(group, MessageChain("请输入正确的群号~"))
            return
    else:
        timers = get_all_timers(group.id)
        result = format_timer_list(timers)

    await app.send_message(group, MessageChain(result))


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[DetectPrefix("yb定时删除")]
))
async def delete_timer_cmd(app: Ariadne, group: Group, member: Member, message: MessageChain):
    """删除定时"""
    if group.id != ADMIN_GROUP:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n此命令只能在管理员群使用哦~")
            ])
        )
        return

    content = message.display.replace("yb定时删除", "").strip()

    if not content:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n请指定要删除的定时ID：\nyb定时删除 [ID]")
            ])
        )
        return

    try:
        timer_id = int(content)
        if delete_timer(timer_id):
            await app.send_message(group, MessageChain(f"✅ 定时 [{timer_id}] 已删除"))
        else:
            await app.send_message(group, MessageChain(f"❌ 删除失败，定时 [{timer_id}] 不存在"))
    except ValueError:
        await app.send_message(group, MessageChain("请输入正确的定时ID~"))


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[DetectPrefix("yb定时修改")]
))
async def modify_timer(app: Ariadne, group: Group, member: Member, message: MessageChain):
    """修改定时"""
    if group.id != ADMIN_GROUP:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n此命令只能在管理员群使用哦~")
            ])
        )
        return

    content = message.display.replace("yb定时修改", "").strip()

    if not content:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n📝 修改定时\n\n"
                      "格式：yb定时修改 [ID] 内容 [新消息] 时间 [新时间]\n\n"
                      "示例：yb定时修改 1 内容 早安 时间 08:00\n"
                      "      yb定时修改 1 时间 09:00")
            ])
        )
        return

    try:
        parts = content.split("内容")
        if len(parts) != 2:
            raise ValueError("格式错误")

        id_part = parts[0].strip()
        rest_part = parts[1].strip()

        timer_id = int(id_part)

        new_message = None
        new_time = None

        if "时间" in rest_part:
            time_parts = rest_part.split("时间")
            new_message = time_parts[0].strip()
            new_time = time_parts[1].strip()
        else:
            new_message = rest_part

        if new_time:
            hours, minutes = new_time.split(":")
            if not (0 <= int(hours) < 24 and 0 <= int(minutes) < 60):
                raise ValueError("时间格式不正确")

        if new_message and new_time:
            current_date = datetime.now().date()
            full_time = f"{current_date} {new_time}:00"
            success = update_timer(timer_id, new_message, full_time)
        elif new_message:
            success = update_timer(timer_id, message=new_message)
        elif new_time:
            current_date = datetime.now().date()
            full_time = f"{current_date} {new_time}:00"
            success = update_timer(timer_id, time_created=full_time)
        else:
            await app.send_message(group, MessageChain("请指定要修改的内容~"))
            return

        if success:
            await app.send_message(group, MessageChain(f"✅ 定时 [{timer_id}] 已修改"))
        else:
            await app.send_message(group, MessageChain(f"❌ 修改失败，定时 [{timer_id}] 不存在"))

    except ValueError as e:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain(f"\n格式错误：{str(e)}\n\n"
                      "格式：yb定时修改 [ID] 内容 [新消息] 时间 [新时间]")
            ])
        )


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[DetectPrefix("yb定时新增")]
))
async def add_timer_cross_group(app: Ariadne, group: Group, member: Member, message: MessageChain):
    """跨群新增定时（仅管理员群）"""
    if group.id != ADMIN_GROUP:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n此命令只能在管理员群使用哦~")
            ])
        )
        return

    content = message.display.replace("yb定时新增", "").strip()

    if not content:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain("\n📝 跨群新增定时\n\n"
                      "格式：yb定时新增 [群号] \"[消息]\" [时间]\n\n"
                      "示例：yb定时新增 290591553 \"早安\" 08:00")
            ])
        )
        return

    try:
        pattern = r'^(\d+)\s+"([^"]+)"\s+(\d{1,2}:\d{2})$'
        match = re.match(pattern, content)

        if not match:
            raise ValueError("格式错误")

        target_group_id = int(match.group(1))
        timer_message = match.group(2)
        timer_time = match.group(3)

        hours, minutes = timer_time.split(":")
        if not (0 <= int(hours) < 24 and 0 <= int(minutes) < 60):
            raise ValueError("时间格式不正确")

        current_date = datetime.now().date()
        full_time = f"{current_date} {timer_time}:00"

        if insert_timer(timer_message, target_group_id, member.id, full_time):
            await app.send_message(
                group,
                MessageChain(f"✅ 已在群 {target_group_id} 添加定时\n"
                             f"📝 消息：{timer_message}\n"
                             f"⏰ 时间：{timer_time}")
            )
        else:
            await app.send_message(group, MessageChain("❌ 添加失败，请稍后再试"))

    except ValueError as e:
        await app.send_message(
            group,
            MessageChain([
                At(member.id),
                Plain(f"\n格式错误：{str(e)}\n\n"
                      "格式：yb定时新增 [群号] \"[消息]\" [时间]\n\n"
                      "示例：yb定时新增 290591553 \"早安\" 08:00")
            ])
        )


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[DetectPrefix("yb帮助定时")]
))
async def help_timers(app: Ariadne, group: Group, member: Member):
    """定时功能帮助"""
    help_text = """📋 定时提醒功能帮助 📋

【基础命令】（所有群可用）
yb定时列表 - 查看当前群的定时列表
yb定时 - 新增定时提醒

【管理员命令】（仅群 1134109340）
yb定时列表全部 - 查看所有群的定时
yb定时新增 [群号] "[消息]" [时间] - 跨群新增定时
yb定时修改 [ID] 内容 [消息] 时间 [时间] - 修改定时
yb定时删除 [ID] - 删除定时

【示例】
yb定时 - 新增当前群的定时
yb定时列表 - 查看当前群所有定时
yb定时新增 290591553 "早安" 08:00 - 在指定群新增定时
yb定时修改 1 内容 晚安 时间 22:00 - 修改定时内容和时间"""

    await app.send_message(group, MessageChain(help_text))


@channel.use(ListenerSchema(
    listening_events=[GroupMessage],
    decorators=[MatchContent("yb定时")]
))
async def insert_timer_interactive(app: Ariadne, group: Group, member: Member, message: MessageChain):
    """交互式新增定时"""
    if group.id not in ALLOWED_GROUPS:
        return

    if message.display.strip() == "yb定时":
        await app.send_message(
            group,
            MessageChain("📝 请输入定时内容，格式：\n\"消息\" 时间\n例如：\"早安\" 08:00")
        )

        @Waiter.create_using_function([GroupMessage])
        async def timer_waiter(g: Group, m: Member, msg: MessageChain):
            if group.id == g.id and member.id == m.id:
                return msg

        try:
            ret_msg: MessageChain = await inc.wait(timer_waiter, timeout=30)
        except asyncio.TimeoutError:
            await app.send_message(group, MessageChain("超时录入!"))
            return

        content = ret_msg.display
        try:
            if '"' not in content:
                raise ValueError("文本需要用双引号括起来")

            start = content.index('"') + 1
            end = content.index('"', start)
            timer_message = content[start:end]
            time_created = content[end + 1:].strip()

            hours, minutes = map(int, time_created.split(':'))
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError("时间格式不正确")

            current_date = datetime.now().date()
            full_time = f"{current_date} {time_created}:00"

            if insert_timer(timer_message, group.id, member.id, full_time):
                await app.send_message(
                    group,
                    MessageChain(f"✅ 定时添加成功！\n📝 消息：{timer_message}\n⏰ 时间：{time_created}")
                )
            else:
                await app.send_message(group, MessageChain("❌ 添加失败，请稍后再试"))

        except ValueError as ve:
            await app.send_message(group, MessageChain(f"输入错误: {str(ve)}"))
        except Exception as e:
            await app.send_message(group, MessageChain(f"添加失败: {str(e)}"))


print("定时提醒管理功能已加载")