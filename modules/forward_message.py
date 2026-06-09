# 群友说 创建转发

import random
from datetime import datetime
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Forward, ForwardNode
from graia.saya import Channel, Saya
from graia.saya.builtins.broadcast import ListenerSchema
from graia.ariadne.model import Group, Member
from graia.broadcast.interrupt import InterruptControl

channel = Channel.current()
saya = Saya.current()
inc = InterruptControl(saya.broadcast)

# 触发关键词
TRIGGER_KEYWORD = "群友说"


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def handle_message(app: Ariadne, group: Group, message: MessageChain, member: Member):
    message_str = str(message)
    if message_str.startswith(TRIGGER_KEYWORD):
        data = message_str.replace(TRIGGER_KEYWORD, "").strip()

        fwd_nodeList = [
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain("(以下内容均为叶布的想象)"),
            )
        ]
        member_list = await app.get_member_list(group)
        # 若 member_list 的长度大于 100，则随机抽取 100 个成员
        # if len(member_list) > 100:
        #     selected_members = random.sample(member_list, 100)
        # else:
        #     selected_members = member_list
        #
        # for random_member in selected_members:
        #     if random_member != member:  # 排除 member
        #         fwd_nodeList.append(
        #             ForwardNode(
        #                 target=random_member,
        #                 time=datetime.now(),
        #                 message=MessageChain(f"{data}"),
        #             )
        #         )

        if len(member_list) > 100:
            selected_members = random.sample(member_list, 99)
            for random_member in selected_members:
                if random_member != member:  # 排除 member
                    fwd_nodeList.append(
                        ForwardNode(
                            target=random_member,
                            time=datetime.now(),
                            message=MessageChain(f"{data}"),
                        )
                    )
        else:
            for random_member in member_list:
                if random_member != member:
                    fwd_nodeList.append(
                        ForwardNode(
                            target=random_member,
                            time=datetime.now(),
                            message=MessageChain(f"{data}"),

                        )
                    )
        fwd_nodeList2 = [ForwardNode(
            target=member,
            time=datetime.now(),
            message=MessageChain("(以上内容均为叶布的想象)"),
        ), ForwardNode(
            target=member,
            time=datetime.now(),
            message=MessageChain("123"),
        )]

        # for random_member in member_list:
        #     if random_member != member:  # 排除 member
        #         fwd_nodeList.append(
        #             ForwardNode(
        #                 target=random_member,
        #                 time=datetime.now(),
        #                 message=MessageChain(f"{data}"),
        #             )
        #         )
        message = MessageChain(Forward(nodeList=fwd_nodeList))
        await app.send_message(group, message)
        # await asyncio.sleep(30)
        # await app.recall_message(msg)
