import asyncio
import random
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
from openai import AsyncOpenAI
from PIL import Image
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Forward, ForwardNode, Image as GraiaImage, Plain, Source
from graia.ariadne.message.parser.twilight import ElementMatch, FullMatch, Twilight, WildcardMatch
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema

channel = Channel.current()

tarot_cards = [
    "愚者", "魔术师", "女祭司", "女皇", "皇帝", "教皇", "恋人", "战车",
    "力量", "隐士", "命运之轮", "正义", "倒吊人", "死神", "节制", "魔鬼",
    "高塔", "星星", "月亮", "太阳", "审判", "世界"
]


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / "config" / "tarot.yaml"
    if not config_path.exists():
        default_config = {
            "api": {
                "api_key": "your_api_key",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
            },
            "temperature": 1.2,
            "allowed_groups": [],
            "card_authors": {},
            "draw_history": {},
            "image_server_url": "http://baibai.pinkcandy.top:80",
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        return default_config

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    config.setdefault("card_authors", {})
    config.setdefault("draw_history", {})
    config.setdefault("image_server_url", "http://8.134.132.129:80")
    config.pop("reservations", None)
    return config


async def save_config(config):
    """异步保存配置文件"""

    def _save():
        config_path = Path(__file__).parent / "config" / "tarot.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_to_save = dict(config)
        config_to_save.pop("reservations", None)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_to_save, f, allow_unicode=True, default_flow_style=False)

    await asyncio.to_thread(_save)


config = load_config()

client = AsyncOpenAI(
    api_key=config["api"]["api_key"],
    base_url=config["api"]["base_url"],
)

TEMPERATURE = config["temperature"]
ALLOWED_GROUPS = config["allowed_groups"]

TAROT_IMAGE_DIR = Path("modules/tarot_cards")
TAROT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = Path("modules/temp_img")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CARD_VERSION_PATTERN = re.compile(r"^(?P<base>.+?)(?P<version>\d+)$")


def parse_card_version(versioned_name: str):
    match = CARD_VERSION_PATTERN.fullmatch(versioned_name)
    if not match:
        return None, None
    return match.group("base"), int(match.group("version"))


def normalize_versioned_card_name(card_name: str) -> str:
    card_name = card_name.strip()
    if not card_name:
        return card_name
    base_name, version = parse_card_version(card_name)
    if base_name in tarot_cards and version is not None:
        return f"{base_name}{version}"
    if card_name in tarot_cards:
        return f"{card_name}1"
    return card_name


def get_card_image_path(versioned_card_name: str) -> Path:
    return TAROT_IMAGE_DIR / f"{versioned_card_name}.png"


def list_card_versions(card_name: str):
    versions = []
    for path in TAROT_IMAGE_DIR.glob(f"{card_name}*.png"):
        versioned_name = path.stem
        base_name, version = parse_card_version(versioned_name)
        if base_name == card_name and version is not None:
            versions.append((version, versioned_name, path))
    versions.sort(key=lambda item: item[0])
    return versions


def has_any_card_image(card_name: str) -> bool:
    return bool(list_card_versions(card_name))


def get_next_versioned_card_name(card_name: str) -> str:
    existing_versions = list_card_versions(card_name)
    next_version = existing_versions[-1][0] + 1 if existing_versions else 1
    return f"{card_name}{next_version}"


def choose_version_for_draw(card_name: str) -> str:
    versions = [versioned_name for _, versioned_name, _ in list_card_versions(card_name)]
    if not versions:
        return f"{card_name}1"

    history = config.setdefault("draw_history", {}).setdefault(card_name, [])
    used_versions = [item for item in history if item in versions]
    available_versions = [item for item in versions if item not in used_versions]

    if not available_versions:
        history.clear()
        available_versions = versions.copy()

    selected_version = random.choice(available_versions)
    history.append(selected_version)
    return selected_version


def migrate_legacy_images_and_config():
    changed = False

    for card_name in tarot_cards:
        legacy_path = TAROT_IMAGE_DIR / f"{card_name}.png"
        versioned_path = get_card_image_path(f"{card_name}1")
        if legacy_path.exists() and not versioned_path.exists():
            legacy_path.rename(versioned_path)
            changed = True

        if card_name in config.get("card_authors", {}) and f"{card_name}1" not in config["card_authors"]:
            config["card_authors"][f"{card_name}1"] = config["card_authors"].pop(card_name)
            changed = True

    valid_history = {}
    for card_name, history in config.get("draw_history", {}).items():
        if card_name not in tarot_cards:
            changed = True
            continue
        valid_versions = {name for _, name, _ in list_card_versions(card_name)}
        filtered_history = [item for item in history if item in valid_versions]
        valid_history[card_name] = filtered_history
        if filtered_history != history:
            changed = True

    config["draw_history"] = valid_history
    return changed


async def compress_image(image_path: Path, max_size: int = 300) -> str:
    """异步压缩图片到指定最大尺寸"""
    compressed_path = OUTPUT_DIR / f"compressed_{image_path.name}"
    if compressed_path.exists() and compressed_path.stat().st_mtime >= image_path.stat().st_mtime:
        return str(compressed_path)

    def _compress():
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background.convert("RGB")
            else:
                img = img.convert("RGB")

            img.thumbnail((max_size, max_size), Image.LANCZOS)
            img.save(compressed_path, "JPEG", quality=75, optimize=True)

        return str(compressed_path)

    return await asyncio.to_thread(_compress)


async def create_reversed_card(versioned_card_name: str) -> str | None:
    """异步创建逆位牌面图片"""
    card_path = get_card_image_path(versioned_card_name)
    if not card_path.exists():
        return None

    def _create():
        with Image.open(card_path) as original_image:
            reversed_image = original_image.rotate(180)
            output_path = OUTPUT_DIR / f"{versioned_card_name}_逆位.png"
            reversed_image.save(output_path)
            return str(output_path)

    return await asyncio.to_thread(_create)


async def get_card_image(versioned_card_name: str, is_reversed: bool = False) -> str | None:
    """异步获取牌面图片路径"""
    card_path = get_card_image_path(versioned_card_name)
    if not card_path.exists():
        return None
    if is_reversed:
        return await create_reversed_card(versioned_card_name)
    return str(card_path)


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def tarot_handler(app: Ariadne, group: Group, message: MessageChain):
    msg_text = message.display.strip()

    if msg_text == "yb抽塔罗牌":
        try:
            selected_card = random.choice(tarot_cards)
            selected_version = choose_version_for_draw(selected_card)
            position = random.choice(["正位", "逆位"])

            current_time_str = time.strftime("%H:%M")
            current_date_str = time.strftime("%Y-%m-%d")

            tarot_prompt = (
                f"你是一只毛绒绒的叶伊布,你的名字叫机叶,在咖啡馆工作,主人叫白白,你可爱且博学多闻.\n"
                f"今天是{current_date_str},现在的时间是{current_time_str}.\n"
                f"用户抽到了塔罗牌 '{selected_card}' {position},请你用一句话简短描述这张塔罗牌的含义以及用户当天的运气,"
                "保持可爱的语气,不要使用颜文字,不要使用感叹号."
            )

            response = await client.chat.completions.create(
                model=config["api"]["model"],
                messages=[
                    {"role": "system", "content": tarot_prompt},
                    {
                        "role": "user",
                        "content": f"我抽到了塔罗牌 '{selected_card}' {position},请告诉我它的含义和今天的运气。",
                    },
                ],
                temperature=TEMPERATURE,
                stream=False,
            )

            ai_response = response.choices[0].message.content.strip()
            message_chain = [
                Plain(f"🎋 你抽到了塔罗牌 {selected_card} {position}\n当前牌面版本: [{selected_version}] 上传者: {config.get('card_authors', {}).get(selected_version, '未知')}\n{ai_response}")
            ]

            card_image = await get_card_image(selected_version, position == "逆位")
            if card_image:
                message_chain.append(GraiaImage(path=card_image))

            await save_config(config)
            await app.send_message(group, MessageChain(message_chain))
        except Exception as e:
            await app.send_message(group, MessageChain([Plain(f"❌ 抽塔罗牌时出错: {str(e)}")]))


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
async def tarot_add_handler(app: Ariadne, group: Group, member: Member, message: MessageChain, source: Source):
    try:
        msg_text = message.display.strip()

        if not msg_text.startswith("yb添加塔罗牌图片"):
            return

        parts = msg_text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await app.send_message(
                group,
                MessageChain("❌ 指令格式有误，请使用: yb添加塔罗牌图片 [卡牌名称] 并附带图片"),
                quote=source.id,
            )
            return

        card_name_str = parts[1].strip().split()[0]
        if card_name_str not in tarot_cards:
            await app.send_message(
                group,
                MessageChain(f"❌ 无效的卡牌名称 '{card_name_str}'，有效卡牌: {', '.join(tarot_cards)}"),
                quote=source.id,
            )
            return

        if GraiaImage not in message:
            await app.send_message(
                group,
                MessageChain("❌ 请在发送指令时附带塔罗牌图片"),
                quote=source.id,
            )
            return

        image_element = message[GraiaImage][0]
        versioned_card_name = get_next_versioned_card_name(card_name_str)
        target_path = get_card_image_path(versioned_card_name)

        try:
            if hasattr(image_element, "url") and image_element.url:

                async def _download_and_save_url():
                    def _sync():
                        response = requests.get(image_element.url, timeout=30)
                        response.raise_for_status()
                        from io import BytesIO

                        with Image.open(BytesIO(response.content)) as img_obj:
                            img_obj.save(target_path)

                    return await asyncio.to_thread(_sync)

                await _download_and_save_url()
            elif hasattr(image_element, "path") and image_element.path:

                async def _save_from_path():
                    def _sync():
                        with Image.open(image_element.path) as img_obj:
                            img_obj.save(target_path)

                    return await asyncio.to_thread(_sync)

                await _save_from_path()
            else:
                raise ValueError("未找到可用的图片来源")

            config.setdefault("card_authors", {})[versioned_card_name] = {
                "user_id": member.id,
                "user_name": member.name or member.display,
                "base_card": card_name_str,
            }
            config.setdefault("draw_history", {}).setdefault(card_name_str, [])
            await save_config(config)

            await app.send_message(
                group,
                MessageChain(
                    f"✅ 成功添加 '{versioned_card_name}' 的塔罗牌图片\n"
                    f"原始卡牌: {card_name_str}\n"
                    f"添加者: {member.name or member.display}"
                ),
                quote=source.id,
            )
        except Exception as image_error:
            await app.send_message(
                group,
                MessageChain(f"❌ 图片保存失败，请重试: {str(image_error)}"),
                quote=source.id,
            )
    except Exception as e:
        await app.send_message(
            group,
            MessageChain(f"❌ 添加图片时出错: {str(e)}"),
            quote=source.id,
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
                    message=MessageChain("🎋 塔罗牌列表"),
                )
            ]

            total_versions = 0
            server_url = config.get("image_server_url", "").rstrip("/")

            for card in tarot_cards:
                versions = list_card_versions(card)
                total_versions += len(versions)

                if not versions:
                    fwd_node_list.append(
                        ForwardNode(
                            target=member,
                            time=datetime.now(),
                            message=MessageChain(f"🎋 {card}\n当前还没有上传任何版本"),
                        )
                    )
                    continue

                lines = [f"🎋 {card} ({len(versions)} 个版本)"]
                for _, versioned_name, image_path in versions:
                    author = config.get("card_authors", {}).get(versioned_name, {})
                    author_name = author.get("user_name", "未知")
                    line = f"{versioned_name} - 上传者: {author_name}"
                    if server_url:
                        line += f"\n🔗 {server_url}/{quote(image_path.name)}"
                    lines.append(line)

                fwd_node_list.append(
                    ForwardNode(
                        target=member,
                        time=datetime.now(),
                        message=MessageChain("\n".join(lines)),
                    )
                )

            fwd_node_list.append(
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain(f"共 {len(tarot_cards)} 张塔罗原始牌，已上传 {total_versions} 个图片版本"),
                )
            )

            await app.send_message(group, MessageChain(Forward(nodeList=fwd_node_list)))
        except Exception as e:
            await app.send_message(group, MessageChain([Plain(f"❌ 获取塔罗牌列表时出错: {str(e)}")]))


_migration_changed = migrate_legacy_images_and_config()
if _migration_changed:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(save_config(config))
    else:
        loop.create_task(save_config(config))
