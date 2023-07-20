from urllib.parse import urlparse
import requests


import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By


from tools.utils import logger
from tools.exceptions import MangaNotFound, InvalidMangaUrl
from bs4 import BeautifulSoup
from fake_headers import Headers
import re
from urllib.parse import quote_plus
from .base_source import BaseSource
from .utils import MangaInfo, Chapter, scraper, static_exists, exists


class MangaNato(BaseSource):
    domain = "manganato.com"
    alternate_domains = ["chapmanganato.com"]

    def __init__(self, url: str):
        url = MangaNato.valid_url(url)
        super().__init__(url)
        self.headers["referer"] = f"https://{self.alternate_domains[0]}/"


    @staticmethod
    def valid_url(url: str) -> str:
        parse = urlparse(url)
        parts = parse.path.replace("//", "/").split("/")[1:]

        if len(parts) == 1:
            return url
        elif len(parts) > 1:
            return f"{parse.scheme}://{parse.netloc}/{parts[0]}"
        else:
            raise InvalidMangaUrl(f"Invalid url: {url}")

    @staticmethod
    @static_exists("https://manganato.com/getstorysearchjson")
    def search(query: str) -> list[MangaInfo]:
        url = "https://manganato.com/getstorysearchjson"
        headers = Headers().generate()
        update = {
            "Referer": "https://manganato.com/",
            "Origin": "https://manganato.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        headers.update(update)

        data = {
            "searchword": query,
        }
        results = []
        try:
            res = requests.post(url, headers=headers, data=data)
            res.raise_for_status()
            result = res.json()["searchlist"]

            for r in result:
                m = MangaInfo(
                    title=re.sub(r"<[^>]*>", "", r["name"]).strip().upper(),
                    url=r["url_story"],
                )
                m.cover_url = r["image"]
                m.authors = [re.sub(r"<[^>]*>", "", r["author"]).strip().upper()]
                m.last_chapter = r["lastchapter"]

                results.append(m)

        except Exception as e:
            logger.error(f"Error searching for {query} on {MangaNato.domain}: {e}")

        if len(results) == 0:
            logger.warning(f"No results found for {query} on {MangaNato.domain}")

        return results

    @property
    def _id(self) -> str:
        url = self.url
        if self.url.endswith("/"):
            url = self.url[:-1]
        return url.split("/")[-1].replace("manga-", "")


    @classmethod
    def id_to_url(cls,id: str) -> str:
        return super().id_to_url(id).replace(cls.domain, cls.alternate_domains[0]).replace("manga/", "manga-")

    @exists
    def get_info(self) -> MangaInfo:
        try:
            res = scraper.get(self.url)
            soup = BeautifulSoup(res.text, "html.parser")  # type: ignore

            # story-info-left
            img = soup.select_one(".info-image img")  # type: ignore
            cover_url: str = img.get("src")  # type: ignore
            info = soup.select_one(".story-info-right")  # type: ignore

            title = info.find("h1").text.strip()  # type: str # type: ignore

            alt = ""
            author = ""
            status = ""
            genre = ""

            trs = info.find_all("tr")  # type: ignore
            for tr in trs:
                label = tr.select_one(".table-label").text.strip()
                value = tr.select_one(".table-value").text.strip()
                if "Alt" in label:
                    alt = value
                elif "Author" in label:
                    author = value
                elif "Status" in label:
                    status = value
                elif "Genre" in label:
                    genre = value

            # story-info-right-extent
            info2 = soup.select_one(".story-info-right-extent")  # type: ignore
            ptags = info2.find_all("p")  # type: ignore
            updated = ptags[0].text.strip()
            views = ptags[1].text.strip()
            rating = ptags[3].text.strip()

            description = (
                soup.select_one(".panel-story-info-description")
                .text.replace("Description :", "")  # type: ignore
                .strip()
            )

            chapters_block = soup.select_one(".panel-story-chapter-list")
            chapters_lis = chapters_block.find_all("li")[::-1]  # type: ignore
            chapters = []
            for chapter in chapters_lis:
                atag = chapter.find("a")  # type: ignore
                chapter_url = atag.get("href")  # type: ignore
                if chapter_url.endswith("/"):
                    chapter_url = chapter_url[:-1]
                chapter_title = atag.text.strip()  # type: ignore
                chapter_views = chapter.select_one(".chapter-view").text.strip()  # type: ignore
                chapter_upload_date = chapter.select_one(".chapter-time").text.strip()  # type: ignore
                chapters.append(
                    Chapter(
                        url=chapter_url,
                        source=self,
                        title=chapter_title,
                        views=chapter_views,
                        date=chapter_upload_date,
                    )
                )

            if ";" in alt:
                alt = alt.split(";")
            else:
                alt = [alt]

            m = MangaInfo(title=title, url=self.url)
            m.alternative_titles = [i.strip() for i in alt]
            m.authors = [i.strip() for i in author.split(",")]
            m.genres = [i.strip() for i in genre.split("-")]
            m.status = status
            m.description = description
            m.cover_url = cover_url
            m.last_updated = updated
            m.views = views
            m.rating = rating
            m.chapters = chapters

            return m

        except Exception as e:
            logger.error(f"Error getting manga info for {self.url}: {e}")
            raise MangaNotFound(f"Manga not found: {self.url}")

    @exists
    def get_chapter_img_urls(self, chapter_url: str) -> list:
        if chapter_url.startswith("/"):
            chapter_url = f"{self.url}{chapter_url}"

        try:
            res = scraper.get(chapter_url)
            soup = BeautifulSoup(res.text, "html.parser")
            imgs = soup.select(".container-chapter-reader img")  # type: ignore
            imgs = [i.get("src") for i in imgs]  # type: ignore
            imgs: list[str] = [i for i in imgs if self._id in i]  # type: ignore

        except Exception as e:
            logger.error(
                f"Error getting chapter images for {chapter_url}: {e}",
            )
            imgs = []

        return imgs



class ONEkissmanga(BaseSource):
    domain = "1stkissmanga.me"
    alternate_domains = ["1stkissmanga.com", "1stkissmanga.io"]

    def __init__(self, url: str):
        super().__init__(url)

    @property
    def _id(self) -> str:
        parts = self.url.split("/")
        return parts[-1] or parts[-2]


    @staticmethod
    @static_exists("https://1stkissmanga.me/wp-admin/admin-ajax.php")
    def search(query: str) -> list[MangaInfo]:
        search_url = "https://1stkissmanga.me/wp-admin/admin-ajax.php"
        data = {"action": "wp-manga-search-manga", "title": query}
        results = []
        try:
            headers = Headers().generate()
            headers.update(
                {
                    "referer": "https://1stkissmanga.me/",
                    "x-requested-with": "XMLHttpRequest",
                    "content-type": "application/x-www-form-urlencoded;",
                    "origin": "https://1stkissmanga.me",
                }
            )

            res = scraper.post(search_url, data=data, headers=headers)
            res.raise_for_status()
            result = res.json()["data"]

            if result[0].get("error", False):
                raise Exception(result[0].get("message", "Unknown error"))

            for r in result:
                m = MangaInfo(title=r["title"], url=r["url"])
                results.append(m)

        except Exception as e:
            logger.error(f"Error searching for {query} on {ONEkissmanga.domain}: {e}")

        return results

    @exists
    def get_info(self) -> MangaInfo:
        try:
            soup = BeautifulSoup(scraper.get(self.url).content, "html.parser")
            # Get the title
            title = soup.find(class_="post-title").text.strip()  # type: ignore

            # Get the cover URL
            cover_url: str = soup.find("div", class_="summary_image").find("img")["src"]  # type: ignore

            post_contents = soup.select(".post-content_item .summary-content")
            rating_rank = post_contents[0].text.strip().split()[1]
            alternatives = post_contents[2].text.strip().split(";")
            authors = post_contents[3].text.strip().split(",")
            artists = post_contents[4].text.strip().split(",")
            genre = post_contents[5].text.strip()
            type_ = post_contents[6].text.strip()
            tags = post_contents[7].text.strip().split(",")
            release = post_contents[8].text.strip()
            status = post_contents[9].text.strip()

            total_comments = soup.find("div", class_="count-comment").text.strip()  # type: ignore
            total_bookmarked = soup.find("div", class_="add-bookmark").text.strip()  # type: ignore
            description = soup.select_one(".description-summary .summary__content").text.strip()  # type: ignore

            chapter_list = soup.select(".wp-manga-chapter")[::-1]  # type: ignore
            chapters = []
            for chapter in chapter_list:
                ch = chapter.find("a")
                ch_url = ch["href"]  # type: ignore
                if ch_url.endswith("/"):  # type: ignore
                    ch_url = ch_url[:-1]
                ch_title = ch.text.strip()  # type: ignore
                ch_date = chapter.select_one(".chapter-release-date").text.strip()  # type: ignore
                chapters.append(Chapter(url=ch_url, source=self, title=ch_title, date=ch_date))  # type: ignore

            m = MangaInfo(title=title, url=self.url)
            m.cover_url = cover_url
            m.alternative_titles = alternatives
            m.authors = authors
            m.artists = artists
            m.genres = [i.strip() for i in genre.split(",")]
            m.tags = tags
            m.status = status
            m.description = description
            m.chapters = chapters
            m.rating = rating_rank
            m.last_updated = release
            m.total_comments = total_comments
            m.total_bookmarked = total_bookmarked
            m.type = type_

            return m

        except Exception as e:
            logger.error(f"Error getting manga info for {self.url}: {e}")
            raise MangaNotFound(f"Manga not found: {self.url}")

    @exists
    def get_chapter_img_urls(self, chapter_url: str) -> list:
        if chapter_url.startswith("/"):
            chapter_url = f"{self.url}{chapter_url}"

        try:
            res = scraper.get(chapter_url)
            soup = BeautifulSoup(res.text, "html.parser")
            imgs = soup.select(".entry-content img")  # type: ignore
            imgs = [i.get("src") for i in imgs]  # type: ignore

        except Exception as e:
            logger.error(f"Error getting chapter images for {chapter_url}: {e}")
            imgs = []

        return imgs


class Bato(BaseSource):
    domain = "bato.to"
    alternate_domains = ["battwo.com", "batotwo.com", "batotoo.com", "mto.to", "comiko.net", "mangatoto.com"]

    def __init__(self, url: str):
        super().__init__(url)
        self.use_selenium_in_get_chapter_img_urls = True


    @property
    def _id(self) -> str:
        parts = self.url.split("/")
        return "_".join(parts[-2:])


    @staticmethod
    def id_to_url(id: str) -> str:
        return (
            f"https://{Bato.domain}/series/{id.replace('bato_', '').replace('_', '/')}"
        )

    @staticmethod
    @static_exists("https://bato.to/search")
    def search(query: str) -> list[MangaInfo]:
        url = "https://bato.to/search?word=" + quote_plus(query)

        results = []
        try:
            res = scraper.get(url)
            soup = BeautifulSoup(res.text, "html.parser")
            slist = soup.select_one("#series-list")
            if not slist:
                raise Exception("No results found")

            items = slist.select(".item.no-flag")  # type: ignore

            for item in items:
                atag = item.select_one(".item-text > a")
                title = atag.text  # type: ignore
                link: str = ""
                alink = atag["href"]  # type: ignore
                if alink.startswith("/"):  # type: ignore
                    link = f"https://{Bato.domain}{alink}"
                else:
                    link = alink  # type: ignore

                cover: str = item.select_one(".item-cover > img")["src"]  # type: ignore

                # item alias
                alias = []
                author = []
                ia = item.select(".item-alias")
                if ia:
                    alias = ia[0].select(".text-muted")
                    alias = [i.text for i in alias]

                    if len(ia) > 1:
                        author = ia[1].select(".text-muted")
                        author = [i.text for i in author]

                # item-genre
                genres = []
                tgenres = item.select(".item-genre > span")
                if tgenres:
                    genres = [i.text for i in genres]

                # item-volch latest-chapter
                latest_chapter = ""
                tlatest_chapter = item.select_one(".item-volch > a")
                if tlatest_chapter:
                    latest_chapter = tlatest_chapter.text.strip()  # type: ignore

                m = MangaInfo(title=title, url=link)
                m.cover_url = cover
                m.authors = author
                m.last_chapter = latest_chapter
                m.genres = genres
                m.alternative_titles = alias

                results.append(m)

        except Exception as e:
            logger.error(f"Error searching for {query} in {Bato.domain}: {e}")

        return results

    @exists
    def get_info(self) -> MangaInfo:
        try:
            res = scraper.get(self.url)
            soup = BeautifulSoup(res.text, "html.parser")

            # .attr-cover
            cover_url = ""
            cover_src = soup.select_one(".attr-cover img")
            if cover_src:
                cover_url = cover_src["src"]

            # h1 item-title
            title = ""
            title_h3 = soup.select_one("h3.item-title")
            if title_h3:
                title = title_h3.text.strip()

            summary = ""
            info = soup.select_one(".detail-set")
            infos = {
                "Rank": "",
                "Authors": "",
                "Artists": "",
                "Genres": "",
                "Translated language": "",
                "Original language": "",
                "Original work": "",
            }
            if info:
                items = info.select(".attr-item")

                for item in items:
                    h = item.select_one(".text-muted")
                    if h:
                        h = h.text.strip().replace(":", "")  # type: ignore
                        val = item.select_one("span").text.replace("\n", "").replace("\r", "").strip()  # type: ignore

                        infos[h] = val

                # div mt-3
                sdiv = info.select_one("div.mt-3")
                if sdiv:
                    summary = sdiv.text.strip()

            genres = [i for i in infos["Genres"].split(",")]
            authors = [i for i in infos["Authors"].split(",")]
            artists = [i for i in infos["Artists"].split(",")]
            rank = infos["Rank"]
            original_language = infos["Original language"]
            translated_language = infos["Translated language"]
            status = infos["Original work"]

            chapters = []

            citems = soup.select(".main > .item")[::-1]
            for c in citems:
                chtitle: str = ""
                link: str = ""
                atag = c.select_one("a")
                if atag:
                    chtitle = atag.text.strip()
                    link = atag["href"]  # type: ignore

                if link.startswith("/"):
                    link = f"https://{Bato.domain}{link}"

                extra = c.select_one(".extra")
                views: str = ""
                date: str = ""
                if extra:
                    views = extra.select("span i")  # type: ignore
                    views = " ".join([i.text for i in views])  # type: ignore
                    date = extra.select_one("i.ps-3").text.strip()  # type: ignore

                chapters.append(
                    Chapter(
                        title=chtitle, url=link, views=views, date=date, source=self
                    )
                )

            m = MangaInfo(title=title, url=self.url)
            m.cover_url = cover_url  # type: ignore
            m.rank = rank
            m.authors = authors
            m.artists = artists
            m.genres = genres
            m.original_language = original_language
            m.translated_language = translated_language
            m.status = status
            m.description = summary
            m.chapters = chapters

            return m

        except Exception as e:
            logger.error(f"Error getting manga info for {self.url}: {e}")
            raise MangaNotFound(f"Manga not found: {self.url}")

    @exists
    def get_chapter_img_urls(self, chapter_url: str, **kw) -> list[str]:
        results = []
        for i in range(2):
            try:
                driver = kw.get("driver", None)
                if not driver:
                    raise Exception(f"Cannot get img urls in {Bato.domain} without driver")
                driver.get(chapter_url)
                imgs = driver.find_elements(By.XPATH, "//div[@id='viewer']//img")
                for img in imgs:
                    results.append(img.get_attribute("src"))
                    
                if results:
                    break
            except Exception as e:
                logger.error(f"Error getting chapter image urls for {chapter_url}: {e}")

        if "pbar" in kw:
            kw["pbar"].update(1)
        return results
