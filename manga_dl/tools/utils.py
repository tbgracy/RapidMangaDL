import json
import time
from typing import Union
from PIL import Image, ImageDraw, ImageFont
import textwrap
import hashlib
import logging
import os
import colorama
import re
import math
from tqdm.auto import tqdm
import threading


from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from uuid import uuid4
import atexit

_utils_path = os.path.dirname(os.path.abspath(__file__))
error_img_path = os.path.join(os.path.dirname(_utils_path), "public", "error.png")


# get a path for appdata
def get_appdata_path():
    # appdata path is user home directory
    appdata_path = os.path.expanduser("~")
    # if windows
    if os.name == "nt":
        appdata_path = os.path.join(appdata_path)
    # if linux
    elif os.name == "posix":
        appdata_path = os.path.join(appdata_path)
    # if mac
    elif os.name == "mac":
        appdata_path = os.path.join(appdata_path)
    
    return appdata_path

def get_app_path():
    appdata_path = get_appdata_path()
    app_path = os.path.join(appdata_path, "manga-dl")
    if not os.path.exists(app_path):
        os.makedirs(app_path)
    return app_path


def auto_scaled_divide(value):
    scaling_factor = math.log10(1 + abs(value)) * 0.5
    return math.ceil(value // scaling_factor)


def replace_unimportant(text: str, but: Union[list, None] = None) -> str:
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


# LOGGER_NAME, LOGGING_LEVEL, RETRY_COUNT
logger_name = os.environ.get("LOGGER_NAME", "manga")
logging_level = os.environ.get("LOGGING_LEVEL", "DEBUG")

logger = logging.getLogger(logger_name)
logger.setLevel(logging_level)

file_handler = logging.FileHandler(os.path.join(get_app_path(), "manga.log"))
stream_handler = logging.StreamHandler()

formatter = ColorFormatter(
    "[%(asctime)s | %(filename)s:%(lineno)s (%(funcName)s)] %(levelname)s - %(message)s",
    datefmt="%I:%M %p",
)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


def create_failure_image(failure_path, url):
    img = Image.open(error_img_path)

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
            logger.error(f"Failed to delete {path}: {e}")


def get_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def get_file_name(url: str, check_extension: bool = False):
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
        logger.error(f"Error while compressing {img_path}: {e}")
        return None


def compress_file_path(file_path):
    name, ext = os.path.splitext(file_path)
    if not name.endswith("_compressed"):
        name += "_compressed"
    return name + ext


def http_split(txt, sep):
    parts = txt.strip().split(f"{sep}http")
    url1 = parts[0]
    rest = []
    for p in parts[1:]:
        rest.append(f"http{p}")
    return [url1] + rest


# create a selenium driver manager
class DriverManager:
    def __init__(self, driver_count: int = -1):
        if driver_count == -1:
            driver_count = (os.cpu_count() or 2) // 2

        self.driver_count = driver_count
        self.manager = {} 
        
        
        self._init = False
        
        logger1 = logging.getLogger("urllib3.connectionpool")
        logger1.setLevel(logging.INFO)

        logger2 = logging.getLogger("selenium.webdriver.remote.remote_connection")
        logger2.setLevel(logging.WARNING)
        
        atexit.register(self._quit)
        
    def init(self):
        if self._init:
            return
        self.service = Service(ChromeDriverManager().install())
        self.init_drivers()
        self._init = True
        

    def create_driver(self):
        return webdriver.Chrome(service=self.service, options=self.driver_options)

    def init_drivers(self):
        for _ in range(self.driver_count):
            self.manager[uuid4().hex] = [
                self.create_driver(),
                False,
            ]  # true if driver is busy

    @property
    def driver_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument('--window-size=1420,1080')
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        return options

    def get_driver(self) -> tuple[str, webdriver.Chrome]:
        self.init()
        
        # check if any driver is free
        for key, value in self.manager.items():
            if not value[1]:
                self.manager[key][1] = True
                return key, value[0]

        # wait for any driver to be free
        return self.wait_for_driver()

    def wait_for_driver(self) -> tuple[str, webdriver.Chrome]:
        while True:
            for key, value in self.manager.items():
                if not value[1]:
                    self.manager[key][1] = True
                    return key, value[0]
            time.sleep(0.1)

    def release_driver(self, key):
        self.manager[key][1] = False
        
    
    def _quit(self):
        if not self._init:
            return
        
        logger.info("Quitting drivers...")
        
        for key, value in self.manager.items():
            try:
                value[0].close()
            except Exception as e:
                logger.error(f"Failed to quit driver {key}: {e}")
        
        self.service.stop()
        atexit.unregister(self._quit)
    
        logger.info("Drivers quit successfully")
    
    def quit(self):
        t = threading.Thread(target=self._quit)
        t.daemon = True
        t.start()
        
driver_manager = DriverManager(1)
