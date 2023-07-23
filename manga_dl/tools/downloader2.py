import os
import shutil
import re
import json
import logging
from multiprocessing import Manager
import hashlib
import aiofiles
import requests
from fake_headers import Headers
import time
from .utils import (
    create_failure_image,
    compress_file_path,
    get_file_name,
    jpeg_compress,
    safe_remove,
    auto_scaled_divide,
    tqdm,
    share_progress_bar,
)
from .models import URLFile
import asyncio
import aiohttp

import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger_name = os.environ.get("LOGGER_NAME", "manga")
logger = logging.getLogger(logger_name)


class Downloader:
    def __init__(
        self,
        urls,
        headers=None,
        download_dir=None,
        check_exists=True,
        jpg_compress=True,
    ):
        self.urls = urls
        self.headers = headers or Headers().generate()
        self.download_dir = download_dir or os.path.join(os.getcwd(), "tmp")
        if not os.path.exists(self.download_dir):
            os.mkdir(self.download_dir)

        self.downloaded_files = Manager().list()
        self.failed_urls = Manager().list()
        self.current_progress = 0
        self.total_urls = len(urls)

    @staticmethod
    def is_file(url):
        # check if url is not a url
        if not re.match(r"^https?://", url):
            if os.path.exists(url) or os.path.exists(compress_file_path(url)):
                return True
        return False

    async def download_file(self, session: aiohttp.ClientSession, url: str, pbar):
        url = url.strip()
        if not self.is_file(url):
            filename = get_file_name(url)
            filepath = os.path.join(self.download_dir, filename)
        else:
            filepath = url

        # print("Downloading", url, filepath)

        cmp_filepath = compress_file_path(filepath)
        isCompressed = False
        isFileExists = False
        if os.path.exists(filepath):
            isFileExists = True

        elif os.path.exists(cmp_filepath):
            isFileExists = True
            filepath = cmp_filepath
            isCompressed = True

        failed = False
        if not isFileExists:
            tmp_path = filepath + ".tmp"
            try:
                timeout = aiohttp.ClientTimeout(
                    total=auto_scaled_divide(self.total_urls)
                )
                async with session.get(url, timeout=timeout) as response:
                    async with aiofiles.open(tmp_path, mode="wb") as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            if chunk:
                                await f.write(chunk)
                shutil.move(tmp_path, filepath)
            except Exception as e:
                logging.error(f"Failed to download {url}: {e}")
                self.failed_urls.append(url)
                failed = True

        if not isCompressed and not failed:
            compressed = jpeg_compress(filepath, cmp_filepath)
            if compressed:
                os.remove(filepath)
                filepath = cmp_filepath
            else:
                logger.error(f"Failed to compress {filepath} {url}")

        if not failed:
            self.downloaded_files.append(URLFile(url, filepath))

        pbar.update(1)
        share_progress_bar(pbar.total, pbar.n, pbar.desc)
        self.total_urls -= 1

    async def download_all(self):
        with tqdm(total=len(self.urls), desc="Downloading") as pbar:
            timeout = aiohttp.ClientTimeout(total=auto_scaled_divide(self.total_urls))
            async with aiohttp.ClientSession(
                headers=self.headers, timeout=timeout
            ) as session:
                tasks = []
                for url in self.urls:
                    task = asyncio.create_task(self.download_file(session, url, pbar))
                    tasks.append(task)
                await asyncio.gather(*tasks)

    @staticmethod
    def download_one(url, headers, download_dir) -> URLFile:
        url = url.strip()
        if not Downloader.is_file(url):
            filename = get_file_name(url)
            filepath = os.path.join(download_dir, filename)
        else:
            filepath = url

        cmp_filepath = compress_file_path(filepath)
        isCompressed = False
        isFileExists = False
        if os.path.exists(filepath):
            isFileExists = True

        elif os.path.exists(cmp_filepath):
            isFileExists = True
            filepath = cmp_filepath
            isCompressed = True

        failed = False
        if not isFileExists:
            try:
                response = requests.get(url, headers=headers)
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

            except Exception as e:
                logging.error(f"Failed to download {url}: {e}")
                failed = True

        if not isCompressed and not failed:
            compressed = jpeg_compress(filepath, cmp_filepath)
            if compressed:
                os.remove(filepath)
                filepath = cmp_filepath
            else:
                logger.error(f"Failed to compress {filepath} {url}")

        if not failed:
            return URLFile(url, filepath)
        else:
            filepath = os.path.join(download_dir, get_file_name(f"{url}_failed"))
            if not os.path.exists(filepath):
                create_failure_image(filepath, url)

            return URLFile(url, filepath)

    def delete_tmp_files(self):
        for file in os.listdir(self.download_dir):
            if file.endswith(".tmp"):
                safe_remove(os.path.join(self.download_dir, file))

    def download(self) -> tuple[list[URLFile], list[str]]:
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

            loop.run_until_complete(self.download_all())

            downloaded_files = list(self.downloaded_files)
            failed_urls = list(self.failed_urls)

            self.downloaded_files = Manager().list()
            self.failed_urls = Manager().list()
            self.current_progress = 0
            self.delete_tmp_files()

            return downloaded_files, failed_urls

        except KeyboardInterrupt:
            self.delete_tmp_files()
            return list(self.downloaded_files), list(self.failed_urls)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


if __name__ == "__main__":
    path = r"F:\Code\Python\manga_downloader\tmp\4acb5a8b3f327de3fcfb0086ece05304.json"
    with open(path, "r") as f:
        urls = json.load(f)

    print("Total:", len(urls))

    s = time.time()
    downloader = Downloader(urls)
    # downloader.download_file()
    e = time.time()
