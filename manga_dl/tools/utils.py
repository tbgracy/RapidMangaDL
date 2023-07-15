from typing import Union
from PIL import Image, ImageDraw, ImageFont
import textwrap
import hashlib
import logging
import os
import colorama
import re

logger = logging.getLogger(os.environ.get("LOGGER_NAME", "tools"))


def replace_unimportant(text: str, but: Union[list,None] = None) -> str:
    # replace all characters except a-z, A-Z, 0-9, and but
    if but is None:
        but = []
    but = [re.escape(c) for c in but]
    buts = "".join(but)
    return re.sub(f"[^{buts}a-zA-Z0-9]", "", text)

class ColorFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._colors = {
            "DEBUG": colorama.Fore.CYAN,
            "INFO": colorama.Fore.GREEN,
            "WARNING": colorama.Fore.YELLOW,
            "ERROR": colorama.Fore.RED,
            "CRITICAL": colorama.Fore.RED,
        }

    def format(self, record):
        levelname = record.levelname
        message = record.msg
        color = self._colors.get(levelname, "")
        message = f"{color}{message}{colorama.Fore.RESET}"
        record.msg = message
        return super().format(record)

def create_failure_image(error_path, failure_path, url):
    img = Image.open(error_path)

    # add url in the 80% of height and centered
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 40)

    text_bbox = draw.textbbox((0, 0), url, font=font)
    w, h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    if w <= img.width:
        draw.text(
            ((img.width - w) / 2, img.height * 0.9), url, font=font, fill="#767676"
        )
    else:
        # multiline
        lines = textwrap.wrap(url, width=img.width // 28)
        y = img.height * 0.85
        for i, text in enumerate(lines):
            textbox = draw.textbbox((0, 0), text, font=font)
            w, h = textbox[2] - textbox[0], textbox[3] - textbox[1]
            draw.text(((img.width - w) / 2, y), text, font=font, fill="#767676")
            y += h

    if img.mode != "RGB":
        img = img.convert("RGB")
    
    img.save(failure_path)
    img.close()
    return failure_path


def safe_remove(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            logger.error(f"Failed to delete {path}", exc_info=True)


def get_hash(url: str) -> str:
    if url[-1] == "/":
        url = url[:-1]
    return hashlib.md5(url.encode()).hexdigest()


def get_file_name(url:str, check_extension:bool=False):
    if not check_extension:
        return hashlib.md5(url.encode()).hexdigest() + ".jpg"
    else:
        _, ex = os.path.splitext(url)
        return hashlib.md5(url.encode()).hexdigest() + ex
    
def jpeg_compress(img_path, save_path):
    try:
        image = Image.open(img_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(save_path, format="JPEG", optimize=True, quality=85)
        image.close()
        return save_path
    except Exception as e:
        logger.exception(f"Error while compressing {img_path}")
        return None
        

def compress_file_path(file_path):
    name, ext = os.path.splitext(file_path)
    if not name.endswith("_compressed"):
        name += "_compressed"
    return name + ext