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

from selenium.webdriver.remote.remote_connection import LOGGER as seleniumLogger

seleniumLogger.setLevel(50)

from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(50)

from selenium import webdriver
from uuid import uuid4
import atexit
import chromedriver_autoinstaller


_utils_path = os.path.dirname(os.path.abspath(__file__))
error_img_path = os.path.join(os.path.dirname(_utils_path), "public", "error.png")


_logger: list[logging.Logger] = []

import threading

lock = threading.Lock()

def get_logger() -> logging.Logger:
    with lock:
        if _logger:
            return _logger[0]
        else:
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
            # check if handlers already exists
            if not logger.handlers:
                logger.addHandler(file_handler)
                logger.addHandler(stream_handler)

            logger.propagate = False
            _logger.append(logger)
            return logger


def share_progress_bar(total_size: float, current_value: float, desc: str = ""):
    os.environ["PROGRESS_BAR"] = json.dumps(
        {"total": total_size, "current": current_value, "desc": desc}
    )


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


class Driver(webdriver.Chrome):
    def __init__(self, options, *args, **kwargs):
        self.options = options
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.usable = True
        self._init = False

    def init(self):
        super().__init__(options=self.options, *self.args, **self.kwargs)
        self.running = True

    def get(self, url):
        if not self._init:
            self.init()
            self._init = True

        super().get(url)


# create a selenium driver manager
class DriverManager:
    def __init__(self, driver_count: int = -1):
        if driver_count == -1:
            driver_count = (os.cpu_count() or 2) // 2

        self.driver_count = driver_count
        self.manager: dict[str, Driver] = {}
        self.chromedriver_installed = True

        if os.environ.get("DRIVER_INSTALLATION_CHECKED", "0") == "0":
            try:
                chromedriver_autoinstaller.install()
            except Exception as e:
                self.chromedriver_installed = False
                logger.error(f"Looks like chrome is not installed: {e}")
            os.environ["DRIVER_INSTALLATION_CHECKED"] = "1"

            
        self.lock = threading.Lock()

    def create_driver(self):
        return Driver(self.driver_options)

    def total_running(self):
        total = 0
        for key, value in self.manager.items():
            if value.running:
                total += 1
        return total

    def get_usable(self):
        for key, value in self.manager.items():
            if value.usable:
                return key, value
        return None, None

    @property
    def driver_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        return options

    def get_driver(self) -> tuple[str, webdriver.Chrome]:
        with self.lock:
            return self.wait_for_driver()

    def wait_for_driver(self) -> tuple[str, webdriver.Chrome]:
        while True:
            total = self.total_running()
            if total < self.driver_count:
                key = get_hash(str(uuid4()))
                driver = self.create_driver()
                driver.usable = False
                self.manager[key] = driver
                return key, driver
            else:
                ky, dr = self.get_usable()
                if ky is not None:
                    return ky, dr  # type: ignore
            time.sleep(0.1)

    def release_driver(self, key: str):
        with self.lock:
            if key in self.manager:
                self.manager[key].usable = True

    def _quit(self):
        logger.info("Quitting drivers...")

        for key, value in self.manager.items():
            value.close()

        logger.info("Drivers quit successfully")
        self.manager = {}

    def quit(self) -> threading.Thread:
        t = threading.Thread(target=self._quit)
        t.daemon = True
        t.start()
        return t


@atexit.register
def quit_drivers():
    try:
        driver_manager.quit()
    except Exception as e:
        logger.error(f"Error while quitting drivers: {e}")

driver_manager = DriverManager(2)
logger = get_logger()
