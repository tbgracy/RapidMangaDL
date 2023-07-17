import json
import time
import aiohttp
import aiofiles
import asyncio
import hashlib
import os
from fake_headers import Headers
from tqdm.auto import tqdm
from multiprocessing import Value
from queue import Queue
import logging
from PIL import Image
import concurrent.futures as cf

logger_name = os.environ.get("LOGGER_NAME", "download")
logging_level = os.environ.get("LOGGING_LEVEL", "DEBUG")
logger = logging.getLogger(logger_name)



def get_file_name(url: str):
    h = hashlib.md5(url.encode()).hexdigest()
    ex = url.split(".")[-1]
    return f"{h}.{ex}"

def jpeg_file(file_path: str):
    ex = os.path.splitext(file_path)[-1]
    return file_path.replace(ex, ".jpg")

class FileManager:
    def __init__(self):
        self.save_queue = Queue()
    
    def delete_file(self, path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
    
    def convert_to_jpeg(self, path: str):
        save_path = jpeg_file(path)
        if os.path.exists(save_path):
            self.save_queue.put((path, save_path))
            return save_path
        try:
            im = Image.open(path)
            im.convert("RGB").save(save_path, "JPEG", optimize=True, quality=85)
            im.close()
            self.delete_file(path)
            self.save_queue.put((path, save_path))
            return save_path
        except Exception as e:
            logger.error(f"Failed to convert {path} to jpeg: {e}")
            self.save_queue.put((path, path))
            return path
        
    def convert_to_jpegs(self, paths: list[str]) -> list[tuple[str, str]]: # list[original_path, jpeg_path]
        with tqdm(total=len(paths), desc="Converting to jpeg") as pbar:
            with cf.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.convert_to_jpeg, path) for path in paths]
                for future in cf.as_completed(futures):
                    pbar.update(1)

        files = {path: path for path in paths}
        while not self.save_queue.empty():
            path, save_path = self.save_queue.get()
            files[path] = save_path
        
        self.clear()
        
        return list(files.items())
    
    def clear(self):
        self.save_queue = Queue()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.clear()
    


class Downloader:
    """
    Download files from urls

    >>> urls = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
    >>> with Downloader(urls) as downloader:
    >>>     downloded_files, failed_urls = downloader.download()
    >>> print(downloaded_files)
    """

    def __init__(self, urls: list[str], headers: dict = None, temp_dir: str = None, check_exists:bool=True, jpg_compress:bool=False):  # type: ignore
        self.urls = urls
        self.check_exists = check_exists
        self.jpeg_compres = jpg_compress
        self.progress_bar = None

        self.total = Value("f", 0)
        self.flag = Value("i", 0)
        self.current = Value("f", 0)

        self.downloaded_files = Queue()
        self.failed_urls = Queue()
        self.headers = headers or Headers().generate()
        if "referer" not in self.headers:
            self.headers["referer"] = "https://chapmanganato.com/"

        self.temp_dir = temp_dir or os.environ.get("TEMP_DIR", "tmp")
        if not os.path.exists(self.temp_dir):
            os.mkdir(self.temp_dir)

        self.retry_count = int(os.environ.get("RETRY_COUNT", 3))

        self.chunk_size = 1024

        # get logger
        self.logger_name = os.environ.get("LOGGER_NAME", "download")
        self.logging_level = os.environ.get("LOGGING_LEVEL", "DEBUG")
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(self.logging_level)

    def share_progress_bar(
        self, total_size: float, current_value: float, desc: str = ""
    ):
        # share with os.environ["PROGRESS_BAR"]
        os.environ["PROGRESS_BAR"] = json.dumps(
            {"total": total_size, "current": current_value, "desc": desc}
        )

    def update_progress_bar(self, total_size: float):
        if self.flag.value == 0:  # type:ignore
            self.progress_bar.reset(total_size)  # type:ignore
            self.total.value += total_size  # type:ignore
            self.flag.value += 1  # type:ignore
        else:
            self.total.value += total_size  # type:ignore
            self.progress_bar.reset(self.total.value)  # type:ignore
            self.progress_bar.update(self.current.value)  # type:ignore
    
        

    async def download_file(self, session: aiohttp.ClientSession, url: str):
        filename = get_file_name(url)
        dest = os.path.join(self.temp_dir, filename)
        if self.check_exists:
            
            flag = False
            if os.path.exists(dest):
                flag = True
                
            if self.jpeg_compres:
                filename2 = jpeg_file(filename)
                dest2 = os.path.join(self.temp_dir, filename2)
                if os.path.exists(dest2):
                    flag = True
                    filename = filename2
                    dest = dest2
            
            if flag:
                size = os.path.getsize(dest)
                self.current.value += size  # type: ignore
                self.update_progress_bar(size)
                self.downloaded_files.put((url, filename))
                return

        dest += ".tmp"
        try:
            async with session.get(url) as response:
                total_size = float(response.headers.get("content-length", 0))
                self.update_progress_bar(total_size)

                async with aiofiles.open(dest, mode="wb") as f:
                    async for data in response.content.iter_chunked(self.chunk_size):
                        await f.write(data)
                        n = len(data)
                        self.progress_bar.update(n)  # type: ignore
                        self.current.value += n  # type: ignore
                        self.share_progress_bar(self.total.value, self.current.value, desc="Downloading files")  # type: ignore
                
            

                os.rename(dest, dest[:-4])
                self.downloaded_files.put((url, filename))
        except Exception as e:
            self.failed_urls.put(url)

    async def download_files(self, urls: list):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = []
            for url in urls:
                tasks.append(self.download_file(session, url))
            await asyncio.gather(*tasks)

    def download(self) -> tuple[list[tuple[str, str]], list[str]]: # tuple[list[tuple[url, filename]], list[failed_urls]]]
        self.progress_bar = tqdm(
            total=1024 * 10, unit="B", unit_scale=True, desc="Downloading files"
        )

        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)    
        loop.run_until_complete(self.download_files(self.urls))

        for i in range(self.retry_count):
            if self.failed_urls.empty():
                break
            urls = []
            self.logger.info(
                f"Retrying for {len(urls)} files... {i+1}/{self.retry_count}"
            )
            while not self.failed_urls.empty():
                urls.append(self.failed_urls.get())
            loop = asyncio.get_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.download_files(urls))

        files: list[tuple[str, str]] = []
        while not self.downloaded_files.empty():
            files.append(self.downloaded_files.get())

        urls: list[str] = []
        while not self.failed_urls.empty():
            urls.append(self.failed_urls.get())

        if len(urls) == 0:
            self.progress_bar.reset(self.total.value)  # type:ignore
            self.progress_bar.update(self.total.value)  # type:ignore
            self.share_progress_bar(self.total.value, self.total.value, desc="Downloading files")  # type:ignore

        self.logger.info(f"Downloaded {len(files)} files")
        self.logger.info(f"Failed to download {len(urls)} files")

        return files, urls

    def clean_up(self):
        for filename in os.listdir(self.temp_dir):
            if filename.endswith(".tmp"):
                os.remove(os.path.join(self.temp_dir, filename))

        self.current.value = 0  # type:ignore
        self.total.value = 0  # type:ignore
        self.flag.value = 0  # type:ignore
        self.progress_bar.close()  # type:ignore

    # enter and exit methods are used to clean up the temp directory
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.clean_up()


if __name__ == "__main__":
    path = r'F:\Code\Python\manga_downloader\tmp\4acb5a8b3f327de3fcfb0086ece05304.json'
    with open(path, "r") as f:
        urls = json.load(f)
    
    print("Total:", len(urls))

    s = time.time()
    with Downloader(urls,temp_dir="downloads") as download:
        files, failed = download.download()
    e = time.time()
    print("Completed:", len(files))
    print("Failed:", len(failed))
    print("Time:", e-s)

    

