import asyncio
import random
import re
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema

channel = Channel.current()


def roll_dice(dice_command):
    default_dice = 100

    pattern = r'^\.rd(\d*)(d(\d+))?([+-]\d+)?$'
    match = re.match(pattern, dice_command)

    if not match:
        return "❌ 格式错误咘！\n📝 正确格式: .rd 或 .rd6 或 .rd2d6 或 .rd3d20+5"

    dice_count = 1
    dice_sides = default_dice
    modifier = 0

    if match.group(1):
        if match.group(2):
            dice_count = int(match.group(1)) if match.group(1) else 1
        else:
            dice_sides = int(match.group(1))

    if match.group(3):
        dice_sides = int(match.group(3))

    if match.group(4):
        modifier = int(match.group(4))

    if dice_count <= 0 or dice_sides <= 0:
        return "❌ 数量和面数必须为整数!"

    if dice_count > 100:
        return "❌ 一次最多只能投100个骰子"

    if dice_sides > 1000:
        return "❌ 骰子面数不能超过1000"

    if abs(modifier) > 1000:
        return "❌ 修正值不能超过±1000"

    results = []
    total = 0

    for i in range(dice_count):
        roll_result = random.randint(1, dice_sides)
        results.append(roll_result)
        total += roll_result

    total += modifier

    if dice_count == 1:
        if modifier == 0:
            result_message = f"🎲 投掷结果: {results[0]}"
        else:
            result_message = f"🎲 投掷结果: {results[0]} {'+' if modifier > 0 else ''}{modifier} = {total}"
    else:
        result_message = f"🎲 投掷{dice_count}d{dice_sides}: {results} = {sum(results)}"
        if modifier != 0:
            result_message += f" {'+' if modifier > 0 else ''}{modifier} = {total}"

    return result_message


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def dice_handler(app: Ariadne, group: Group, message: MessageChain):
    msg_text = message.display.strip()

    if msg_text.startswith('.rd'):
        try:
            result = roll_dice(msg_text)
            await app.send_message(
                group,
                MessageChain([Plain(result)]),
            )
        except Exception as e:
            error_msg = f"❌ qwq: {str(e)}"
            await app.send_message(
                group,
                MessageChain([Plain(error_msg)]),
            )
