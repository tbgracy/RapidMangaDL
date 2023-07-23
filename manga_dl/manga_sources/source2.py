import re
from urllib.parse import quote


import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tools.utils import logger, get_file_name, Driver
from tools.exceptions import MangaNotFound
from bs4 import BeautifulSoup
from .base_source import BaseSource
from .utils import MangaInfo, Chapter, scraper, static_exists, exists
import base64


class MangaKakalot(BaseSource):
    domain = "mangakakalot.to"
    manga_format = "https://{domain}/{ID}"

    def __init__(self, url):
        super().__init__(url)
        self.use_selenium_in_get_chapter_img_urls = True

    @staticmethod
    @static_exists("https://mangakakalot.to/search?keyword=")
    def search(query: str) -> list[MangaInfo]:
        cls = MangaKakalot
        url = f"https://mangakakalot.to/search?keyword={quote(query)}"
        results = []
        try:
            res = scraper.get(url)

            # all atags: url > img: src
            if res:
                soup = BeautifulSoup(res.text, "html.parser")
                inner = soup.find(class_="manga-list")
                items = inner.select(".item") if inner else []  # type: ignore
                for item in items:
                    # .manga-name
                    # .chapter-name

                    # item-poster
                    title: str = ""
                    url: str = ""
                    img: str = "/public/error.png"
                    postert = item.find(class_="item-poster")
                    if postert:
                        atag = postert.find("a")
                        if atag:
                            url = atag["href"]  # type: ignore
                            imgt = atag.find("img")  # type: ignore
                            if imgt:
                                img = imgt["src"]  # type: ignore
                                title = imgt["alt"]  # type: ignore

                    if url.startswith("/"):
                        url = f"https://{cls.domain}{url}"

                    cht = item.find(class_="chapter-name")
                    last_chapter = ""
                    if cht:
                        last_chapter = (
                            cht.text.replace("\n", "").replace("\r", "").strip()
                        )

                    if url and title:
                        results.append(
                            MangaInfo(
                                title, url, cover_url=img, last_chapter=last_chapter
                            )
                        )
        except Exception as e:
            logger.error(f"Error searching for {query} in {cls.domain}: {e}")

        return results

    def get_chapters(self) -> list[Chapter]:
        cid = re.findall(r"\d+", self._id)[0]
        url = f"https://mangakakalot.to/ajax/manga/list-chapter-volume?id={cid}"
        try:
            res = scraper.get(url)
            soup = BeautifulSoup(res.text, "html.parser")

            chd = soup.select_one("#list-chapter-en")
            items = chd.select(".item")[::-1]  # type: ignore
            chapters = []
            for item in items:
                atag = item.find("a")
                url: str = ""
                title = ""
                if atag:
                    url = atag["href"]  # type: ignore
                    title = atag.text.strip()
                timet = item.select_one(".item-time")  # type: ignore
                date = ""
                if timet:
                    date = timet.text.strip()

                if url and title:
                    if url.startswith("/"):
                        url = f"https://{self.domain}{url}"

                    chapters.append(
                        Chapter(url=url, source=self, title=title, date=date)
                    )

            return chapters
        except Exception as e:
            logger.error(f"Error getting chapters for {self.url}: {e}")
            return []

    @exists
    def get_info(self) -> MangaInfo:
        try:
            res = scraper.get(self.url)
            soup = BeautifulSoup(res.text, "html.parser")
            soup = soup.select_one(".detail-box")  # type: ignore

            potert = soup.select_one(".manga-poster > img")  # type: ignore
            cover_url: str = potert["src"] if potert else "/public/error.png"  # type: ignore

            info = soup.select_one(".db-info")  # type: ignore

            title = ""
            alias = []
            titlet = soup.select_one(".manga-name")  # type: ignore
            if titlet:
                title = titlet.text.strip()
            aliast = soup.select_one(".alias")  # type: ignore
            if aliast:
                alias = [aliast.text.strip()]

            infod = {
                "Author(s)": "",
                "Status": "",
                "Published": "",
                "Views": "",
                "Genres": "",
            }

            lines = info.select(".line-content")  # type: ignore
            for content in lines[1:-1]:
                # title
                key = content.select_one(".title")  # type: ignore
                key = key.text.replace(":", "").strip() if key else ""

                # result
                val = content.select_one(".result")
                val = (
                    val.text.replace("\n", "").replace("\r", "").strip() if val else ""
                )

                infod[key] = val

            ratet = lines[-1]
            rate = ratet.select_one(".rate-result")  # type: ignore
            rate = (
                " ".join(re.split(r"\s+", rate.text, flags=re.UNICODE)).strip()
                if rate
                else ""
            )

            infod["Authors"] = [i.strip() for i in infod["Author(s)"].split(",")]  # type: ignore
            infod["Genres"] = [i.strip() for i in infod["Genres"].split(",")]  # type: ignore

            # dbs-content
            description = ""
            dest = soup.select_one(".dbs-content")  # type: ignore
            if dest:
                description = dest.text.strip()

            return MangaInfo(
                url=self.url,
                title=title,
                cover_url=cover_url,
                description=description,
                alternative_titles=alias,
                genres=infod["Genres"],
                authors=infod["Authors"],
                status=infod["Status"],
                rating=rate,
                views=infod["Views"],
                last_updated=infod["Published"],
                chapters=self.get_chapters(),
            )

        except Exception as e:
            raise MangaNotFound(f"Error getting info for {self.url}: {e}")

    @exists
    def get_chapter_img_urls(self, chapter_url: str, **kw) -> list[str]:
        results = []
        got_driver = False
        driver: Driver = kw.get("driver", None)
        for i in range(2):
            try:
                if not driver:
                    raise Exception(
                        f"Cannot get img urls in {self.domain} without driver"
                    )

                got_driver = True
                driver.remove_option("--disable-dev-shm-usage")
                driver.remove_option("--blink-settings=imagesEnabled=false")

                driver.get(chapter_url)
                soup = BeautifulSoup(driver.page_source, "html.parser")

                lst_img = soup.select_one("#list-image")  # type: ignore
                imgs = lst_img.select("img")  # type: ignore
                for img in imgs:
                    results.append(img.get("src", ""))

                # imgs can be stored in canvas
                if not results:
                    try:
                        wait = WebDriverWait(driver, 10)
                        # last card-warp have canvas
                        wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".card-wrap:last-child canvas"))
                        )
                    except Exception as e:
                        logger.error(
                            f"Error waiting for canvas in {chapter_url}: {e}",
                        )

                    canvases = driver.find_elements(By.TAG_NAME, "canvas")
                    for i, canvas in enumerate(canvases):
                        canvas_base64 = driver.execute_script(
                            "return arguments[0].toDataURL('image/jpeg').substring(22);",
                            canvas,
                        )
                        canvas_jpg = base64.b64decode(canvas_base64)

                        filename = get_file_name(f"{chapter_url}_{i}.jpg")
                        filepath = os.path.join(self.temp_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(canvas_jpg)
                        results.append(filepath)

                if results:
                    break

            except Exception as e:
                logger.error(f"Error getting chapter image urls for {chapter_url}: {e}")

        if got_driver:
            driver.usable = True

        if "pbar" in kw:
            kw["pbar"].update(1)
        return results



