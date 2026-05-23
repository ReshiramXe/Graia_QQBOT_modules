import asyncio
import random
import json
import time
import yaml
import requests
from pathlib import Path
from PIL import Image
from openai import AsyncOpenAI
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain, Image as GraiaImage, Source, Forward, ForwardNode
from graia.ariadne.message.parser.twilight import Twilight, FullMatch, ElementMatch, ElementResult, RegexMatch, \
    WildcardMatch
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema

channel = Channel.current()

# 塔罗牌列表
tarot_cards = [
    "愚者", "魔术师", "女祭司", "女皇", "皇帝", "教皇", "恋人", "战车",
    "力量", "隐士", "命运之轮", "正义", "倒吊人", "死神", "节制", "魔鬼",
    "高塔", "星星", "月亮", "太阳", "审判", "世界"
]


# 加载配置
def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config' / 'tarot.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# 加载配置
config = load_config()

# 初始化OpenAI客户端
client = AsyncOpenAI(
    api_key=config['api']['api_key'],
    base_url=config['api']['base_url']
)

# 配置参数
TEMPERATURE = config['temperature']
ALLOWED_GROUPS = config['allowed_groups']

# Tarot card image handling
TAROT_IMAGE_DIR = Path("modules/tarot_cards")
TAROT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = Path("modules/temp_img")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_card_image_path(card_name: str) -> Path:
    return TAROT_IMAGE_DIR / f"{card_name}.png"


def create_reversed_card(card_name: str) -> str:
    card_path = get_card_image_path(card_name)
    if card_path.exists():
        from PIL import Image
        original_image = Image.open(card_path)
        reversed_image = original_image.rotate(180)
        output_path = OUTPUT_DIR / f"{card_name}_逆位.png"
        reversed_image.save(output_path)
        return str(output_path)
    return None


def get_card_image(card_name: str, is_reversed: bool = False) -> str:
    card_path = get_card_image_path(card_name)
    if card_path.exists():
        if is_reversed:
            return create_reversed_card(card_name)
        return str(card_path)
    return None


def is_card_image_available(card_name: str) -> bool:
    return get_card_image_path(card_name).exists()


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def tarot_handler(app: Ariadne, group: Group, message: MessageChain):
    msg_text = message.display.strip()

    if msg_text == "yb抽塔罗牌":
        try:
            # 随机抽取一张塔罗牌
            selected_card = random.choice(tarot_cards)
            # 随机决定正位或逆位
            position = random.choice(["正位", "逆位"])

            # 调用AI来回复
            current_time_str = time.strftime("%H:%M")
            current_date_str = time.strftime("%Y-%m-%d")

            # 构建AI提示
            tarot_prompt = config['tarot_prompt']

            response = await client.chat.completions.create(
                model=config['api']['model'],
                messages=[
                    {"role": "system", "content": tarot_prompt},
                    {"role": "user",
                     "content": f"我抽到了塔罗牌 '{selected_card}' {position},请告诉我它的含义和今天的运气."}
                ],
                temperature=TEMPERATURE,
                stream=False
            )

            ai_response = response.choices[0].message.content.strip()

            # 准备消息内容
            message_chain = [Plain(f"🎴 你抽到了塔罗牌: {selected_card} {position}\n{ai_response}")]

            # 检查是否有牌面图片
            card_image = get_card_image(selected_card, position == "逆位")
            if card_image:
                message_chain.append(GraiaImage(path=card_image))

            # 发送回复
            await app.send_message(
                group,
                MessageChain(message_chain),
            )
        except Exception as e:
            error_msg = f"❌ 抽塔罗牌时出错: {str(e)}"
            await app.send_message(
                group,
                MessageChain([Plain(error_msg)]),
            )


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[
            Twilight(
                FullMatch("yb添加塔罗牌图片"),
                FullMatch(" ", optional=True),
                "card_name" @ WildcardMatch(),
                "img" @ ElementMatch(GraiaImage, optional=True),
            ),
        ],
    )
)
async def tarot_add_handler(app: Ariadne, group: Group, message: MessageChain, source: Source):
    try:
        msg_text = message.display.strip()

        if not msg_text.startswith("yb添加塔罗牌图片"):
            return

        # 查找第一个空格
        space_idx = msg_text.find(" ")
        if space_idx == -1:
            await app.send_message(
                group,
                MessageChain("❌ 指令格式有误，请使用: yb添加塔罗牌图片 [卡牌名称] 并附带图片"),
                quote=source.id
            )
            return

        # 从第一个空格后获取卡牌名称
        card_name_str = msg_text[space_idx:].strip()

        # 再次查找空格，只取第一个空格前的内容
        next_space = card_name_str.find(" ")
        if next_space != -1:
            card_name_str = card_name_str[:next_space].strip()

        if card_name_str not in tarot_cards:
            await app.send_message(
                group,
                MessageChain(f"❌ 无效的卡牌名称 '{card_name_str}'，有效卡牌: {', '.join(tarot_cards)}"),
                quote=source.id
            )
            return

        # 检查是否有图片
        if GraiaImage not in message:
            await app.send_message(
                group,
                MessageChain("❌ 请在发送指令时附带塔罗牌图片"),
                quote=source.id
            )
            return

        image_element = message[GraiaImage][0]

        # 尝试从 URL 获取图片
        try:
            if hasattr(image_element, 'url') and image_element.url:
                response = requests.get(image_element.url)
                response.raise_for_status()
                from io import BytesIO
                img_obj = Image.open(BytesIO(response.content))
                img_obj.save(get_card_image_path(card_name_str))

                await app.send_message(
                    group,
                    MessageChain(f"✅ 成功添加 '{card_name_str}' 的塔罗牌图片！"),
                    quote=source.id
                )
                return
        except Exception as e1:
            print(f"URL 方式下载失败: {e1}")

        # 尝试从 path 获取图片
        try:
            if hasattr(image_element, 'path') and image_element.path:
                img_obj = Image.open(image_element.path)
                img_obj.save(get_card_image_path(card_name_str))

                await app.send_message(
                    group,
                    MessageChain(f"✅ 成功添加 '{card_name_str}' 的塔罗牌图片！"),
                    quote=source.id
                )
                return
        except Exception as e2:
            print(f"路径方式复制失败: {e2}")

        await app.send_message(
            group,
            MessageChain("❌ 图片保存失败，请重试"),
            quote=source.id
        )

    except Exception as e:
        await app.send_message(
            group,
            MessageChain(f"❌ 添加图片时出错: {str(e)}"),
            quote=source.id
        )


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def tarot_list_handler(app: Ariadne, group: Group, message: MessageChain, member: Member):
    msg_text = message.display.strip()

    if msg_text == "yb塔罗牌列表":
        try:
            from datetime import datetime

            fwd_node_list = [
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain("🎴 塔罗牌列表"),
                )
            ]

            for card in tarot_cards:
                message_chain = [Plain(f"🎴 {card}")]
                card_image = get_card_image_path(card)
                if card_image.exists():
                    message_chain.append(GraiaImage(path=str(card_image)))

                fwd_node_list.append(
                    ForwardNode(
                        target=member,
                        time=datetime.now(),
                        message=MessageChain(message_chain),
                    )
                )

            fwd_node_list.append(
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain(f"共 {len(tarot_cards)} 张塔罗牌"),
                )
            )

            await app.send_message(
                group,
                MessageChain(Forward(nodeList=fwd_node_list))
            )
        except Exception as e:
            error_msg = f"❌ 获取塔罗牌列表时出错: {str(e)}"
            await app.send_message(
                group,
                MessageChain([Plain(error_msg)])
            )
