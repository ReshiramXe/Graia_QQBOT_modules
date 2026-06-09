# 生成摸摸gif模块


from pathlib import Path
import re
import requests
import math
import cv2
import numpy as np
from PIL import Image as PILImage, ImageDraw
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image as GraiaImage
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema

channel = Channel.current()


def overlay_gif_on_image(image_path, output_path):
    gif_path = '/home/botin/hand_image/petpet/template.gif'

    image = cv2.imread(image_path)
    image_pil = PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


    new_width = int(image_pil.width * 2 / 5)
    new_height = int(image_pil.height * 2 / 5)
    image_pil = image_pil.resize((new_width, new_height))

    mask = PILImage.new('L', image_pil.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, image_pil.width, image_pil.height), fill=255)
    image_pil.putalpha(mask)

    gif = PILImage.open(gif_path)
    new_frames = []

    for frame_idx in range(gif.n_frames):
        gif.seek(frame_idx)
        gif_frame = gif.convert("RGBA").resize((gif.width * 2, gif.height * 2))

        y_offset = int(15 * math.sin(frame_idx * 0.5))
        current_y = 16 + y_offset

        composite = PILImage.new("RGBA", gif_frame.size)
        composite.paste(image_pil, (0, current_y), image_pil)
        composite.alpha_composite(gif_frame)

        new_frames.append(composite.convert("RGB"))

    new_frames[0].save(
        output_path,
        save_all=True,
        append_images=new_frames[1:],
        duration=gif.info['duration'],
        loop=0
    )


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def handle_message(app: Ariadne, group: Group, message: MessageChain, member: Member):
    TRIGGER_KEYWORD = "yb摸摸"
    message_str = str(message)

    if message_str.startswith(TRIGGER_KEYWORD):
        member_id = message_str.replace(TRIGGER_KEYWORD, "").strip().replace('@', '')
        url = f'http://q1.qlogo.cn/g?b=qq&nk={member_id}&s=640'

        with requests.get(url) as response, open(save_path := f'hand_image/{member_id}.jpg', 'wb') as f:
            f.write(response.content)

        output_path = f'/home/botin/hand_image/petout/{member_id}.gif'
        overlay_gif_on_image(save_path, output_path)
        await app.send_message(group, MessageChain(GraiaImage(path=output_path)))


