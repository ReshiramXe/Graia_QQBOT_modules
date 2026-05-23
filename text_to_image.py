# 帮助


import asyncio
import yaml
import pymysql
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image as GraiaImage
from graia.ariadne.model import Group
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema
from PIL import Image as PILImage, ImageDraw, ImageFont

channel = Channel.current()

def load_config():
    config_path = Path(__file__).parent / 'config' / 'textimage.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
FONT_PATH = config['image']['font_path']
BACKGROUND_COLOR = tuple(config['image']['background_color'])
TEXT_COLOR = tuple(config['image']['text_color'])
FONT_SIZE = config['image']['font_size']
IMAGE_PATH = config['image']['output_path']
DB_CONFIG = config.get('database', {
    'host': '',
    'user': '',
    'passwd': '',
    'port': 3306,
    'db': '',
    'charset': 'utf8'
})


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def textimage(app: Ariadne, group: Group, message: MessageChain):
    if message.display == "叶布功能":
        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            sql = "SELECT content FROM menu"
            cursor.execute(sql)
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            if rows:
                MENU_ITEMS = [row[0] for row in rows]
                formatted_menu_text = '\n\n'.join(MENU_ITEMS)
            else:
                formatted_menu_text = "菜单为空"

            dummy_image = PILImage.new('RGB', (1, 1))
            draw = ImageDraw.Draw(dummy_image)
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

            bbox = draw.textbbox((0, 0), formatted_menu_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            margin = 20
            image_width = text_width + 2 * margin
            image_height = text_height + 2 * margin

            image = PILImage.new('RGB', (image_width, image_height), color=BACKGROUND_COLOR)
            draw = ImageDraw.Draw(image)

            draw.text((margin, margin), formatted_menu_text, font=font, fill=TEXT_COLOR)

            if not os.path.exists(os.path.dirname(IMAGE_PATH)):
                os.makedirs(os.path.dirname(IMAGE_PATH))
            image.save(IMAGE_PATH)

            await app.send_message(
                group,
                MessageChain([GraiaImage(path=IMAGE_PATH)]),
            )

        except Exception as e:
            print(f"An error occurred: {e}")
