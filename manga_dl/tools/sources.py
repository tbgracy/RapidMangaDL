import pprint
from typing import Union
from urllib.parse import urlparse

import requests
from .utils import logger, safe_remove, get_file_name, get_hash
from .exceptions import MangaNotFound, SourceNotFound, InvalidMangaUrl
from cloudscraper import create_scraper
import json
from bs4 import BeautifulSoup
import os
from fake_headers import Headers
import re

scraper = create_scraper(
    browser={"browser": "firefox", "platform": "windows", "mobile": False}
)


class Chapter:
    def __init__(
        self,
        url: str,
        source: "BaseSource",
        title: str = "",
        views: str = "",
        date: str = "",
    ):
        self.url: str = url
        self.title: str = title
        self.views: str = views
        self.date: str = date
        self.source: BaseSource = source

        self._chapter_imgs: list[str] = []
        self._img_filenames = []
        self._img_filenames_not_ordered = []
        self._qimg_filenames_not_ordered = []

        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self.check_chapter_imgs_cache_exists = True
        self.add_filenames_called = False

    @classmethod
    def from_url(cls, url: str):
        source = get_source(url)
        return cls(url, source)

    # compare operator
    def __eq__(self, other: "Chapter"):
        return self.url == other.url

    def __ne__(self, other: "Chapter"):
        return self.url != other.url

    def __hash__(self):
        return hash(self.url)

    @property
    def id(self):
        if self.url.endswith("/"):
            return self.url[:-1].split("/")[-1]
        return self.url.split("/")[-1]

    @property
    def short_name(self):
        # if number in title, retun it or short title
        if self.title:
            if re.search(r"\d+", self.title):
                # return number
                m = re.search(r"\d+", self.title)
                if m:
                    return m.group()

        return re.sub(r"[^A-z]", "_", self.title)

    @property
    def img_filenames(self) -> list[str]:
        if self.add_filenames_called:
            return self._img_filenames
        raise Exception("You must call add_filenames() first")

    @property
    def img_urls(self) -> list[str]:
        if not self._chapter_imgs:
            self._chapter_imgs = self.get_chapter_imgs()
        return self._chapter_imgs

    def _order_files_url(
        self, files: list[tuple[str, str]]
    ):  # filenames: [(url, filename)]
        # map url to filename with order
        chapter_imgs_dict = {img_url: "" for img_url in self.img_urls}
        for img_url, filename in files:
            chapter_imgs_dict[img_url] = filename
        self.add_filenames_called = True
        self._img_filenames = list(chapter_imgs_dict.values())

    def order_files(self):
        self._order_files_url(self._img_filenames_not_ordered)

    def add_file(self, file):  # file: (url, filename)
        self._img_filenames_not_ordered.append(file)

    def _order_qfiles_files(
        self, qfiles: list[tuple[str, str]]
    ):  # qfiles: [(original_filename, new_filename)]
        # map original_filename to new_filename with order
        chapter_imgs_filenames_dict = {filename: "" for filename in self.img_filenames}
        for original_filename, new_filename in qfiles:
            chapter_imgs_filenames_dict[original_filename] = new_filename
        self._img_filenames = list(chapter_imgs_filenames_dict.values())

    def add_qfile(self, qfile):  # qfile: (original_filename, new_filename)
        self._qimg_filenames_not_ordered.append(qfile)

    def order_qfiles(self):
        self._order_qfiles_files(self._qimg_filenames_not_ordered)

    def get_chapter_imgs(self):
        return self.source.get_chapter_img_urls(self.url)

    def __repr__(self):
        return f"<Chapter {self.title}>"

    def __str__(self):
        return pprint.pformat(self.to_json())

    # 0 = url, 1 = title, 2 = views, 3 = date
    def __getitem__(self, index: int) -> str:
        return [self.url, self.title, self.views, self.date][index]

    def __setitem__(self, index: int, value: str) -> None:
        if index == 0:
            self.url = value
        elif index == 1:
            self.title = value
        elif index == 2:
            self.views = value
        elif index == 3:
            self.date = value

    def to_json(self):
        return {
            "url": self.url,
            "title": self.title,
            "views": self.views,
            "date": self.date,
            "source": self.source.to_json(),
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            data["url"],
            get_source(data["url"]),
            data["title"],
            data["views"],
            data["date"],
        )


def _info_path(self: "BaseSource", url: str) -> str:
    return os.path.join(self.temp_dir, f"{get_file_name(url, True)}_info.json")


# creae a check_exists decorator that will take url from the function and check if it exists in the cache
def exists(func):
    def wrapper(*args, **kwargs):
        self: BaseSource = args[0]
        url = self.url
        if len(args) > 1:
            url = args[1]

        if url.startswith("/"):
            url = self.url + url

        path = _info_path(self, url)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    if not data:
                        raise Exception(f"Error loading cache from {path}")
                    return data
            except Exception as e:
                logger.error(f"Error loading info from {path}: {e}")
                safe_remove(path)
        else:
            data = func(*args, **kwargs)
            if data:
                try:
                    with open(path, "w") as f:
                        json.dump(data, f)
                except Exception as e:
                    logger.error(f"Error saving info to {path}: {e}")
                    safe_remove(path)

            return data

    return wrapper


class BaseSource:
    def __init__(self, url: str):
        self.url = url
        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self.headers: dict = Headers().generate()
    
    @property
    def current_domain(self) -> str:
        return urlparse(self.url).netloc

    @property
    def id(self) -> str:
        return f"base_{get_hash(self.url)}"

    @staticmethod
    def is_valid(url: str) -> bool:
        return False

    @staticmethod
    def valid_id(id: str) -> bool:
        return False

    @staticmethod
    def search(query: str) -> list[dict]:
        return []

    def to_json(self) -> dict:
        return {
            "url": self.url,
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(data["url"])

    @staticmethod
    def id_to_url(id: str) -> str:
        return ""

    @exists
    def get_info(self) -> dict:
        return {}

    @exists
    def get_chapter_img_urls(self, chapter_url: str) -> list[str]:
        return []

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.url})"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def all_domains() -> list[str]:
        return []


class MangaNato(BaseSource):
    domain = "manganato.com"
    alternate_domains = ["chapmanganato.com"]
    

    def __init__(self, url: str):
        url = MangaNato.valid_url(url)
        super().__init__(url)
        self.headers["referer"] = f"https://{self.alternate_domains[0]}/"

    @staticmethod
    def is_valid(url: str) -> bool:
        return any(domain in url for domain in MangaNato.all_domains())

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
    def search(query: str) -> list[dict]:
        if "http" in query:
            m = MangaNato(query)
            return [m.get_info()]

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
        filename = get_file_name(f"{url}/{query}.json", True)
        path = os.path.join(os.environ.get("TEMP_DIR", "tmp"), filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    results = json.load(f)
                    if not results:
                        raise Exception(f"No data found in the `{query}` cache in {path}")
                return results
            except Exception as e:
                logger.error(f"Failed to load `{query}` cache from {path}")
        
        
        
        results = []
        try:
            res = requests.post(url, headers=headers, data=data)
            res.raise_for_status()
            result = res.json()["searchlist"]

            for r in result:
                results.append(
                    {
                        "url": r["url_story"],
                        "title": re.sub(r"<[^>]*>", "", r["name"]).strip().upper(),
                        "cover_url": r["image"],
                        "author": re.sub(r"<[^>]*>", "", r["author"]).strip().upper(),
                        "last_chapter": r["lastchapter"],
                    }
                )
            try:
                with open(path, "w") as f:
                    json.dump(results, f)
            except Exception as e:
                logger.error(f"Falied to save search results: {e}")

        except Exception as e:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        result = json.load(f)
                except Exception as e:
                    logger.error(f"Falied to load search results from cache: {e}")
                    os.remove(path)

            else:
                logger.error(f"Falied to load search results from cache: {e}")

        return results

    @property
    def manganato_id(self) -> str:
        url = self.url
        if self.url.endswith("/"):
            url = self.url[:-1]
        return url.split("/")[-1].replace("manga-", "")

    @property
    def id(self) -> str:
        return f"managato_{self.manganato_id}"

    @staticmethod
    def valid_id(id: str) -> bool:
        return id.startswith("managato_")

    @staticmethod
    def id_to_url(id: str) -> str:
        return f"https://chapmanganato.com/manga-{id.replace('managato_', '')}"

    @exists
    def get_info(self) -> dict:
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
                alt = alt.split(";")[0].strip()

            data = {
                "url": self.url,
                "title": title,
                "alternative_title": alt,
                "author": author,
                "status": status,
                "genre": genre,
                "description": description,
                "total_chapters": len(chapters),
                "cover_url": cover_url,
                "updated": updated,
                "views": views,
                "rating": rating,
                "chapters": [c.to_json() for c in chapters],
            }
            return data

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
            imgs: list[str] = [i for i in imgs if self.manganato_id in i]  # type: ignore

        except Exception as e:
            logger.error(
                f"Error getting chapter images for {chapter_url}: {e}",
            )
            imgs = []

        return imgs

    @staticmethod
    def all_domains() -> list[str]:
        return [MangaNato.domain] + MangaNato.alternate_domains


class ONEkissmanga(BaseSource):
    domain = "1stkissmanga.me"
    alternate_domains = ["1stkissmanga.com", "1stkissmanga.io"]

    def __init__(self, url: str):
        super().__init__(url)
        self.headers["referer"] = f"https://{ONEkissmanga.domain}"

    @property
    def id(self) -> str:
        parts = self.url.split("/")
        return f"1stkissmanga_{parts[-1] or parts[-2]}"

    @staticmethod
    def is_valid(url: str) -> bool:
        return any(domain in url for domain in ONEkissmanga.all_domains())

    @staticmethod
    def valid_id(id: str) -> bool:
        return id.startswith("1stkissmanga_")

    @staticmethod
    def id_to_url(id: str) -> str:
        return f"https://{ONEkissmanga.domain}/manga/{id.replace('1stkissmanga_', '')}"

    @staticmethod
    def search(query: str) -> list[dict]:
        search_url = "https://1stkissmanga.me/wp-admin/admin-ajax.php"
        data = {"action": "wp-manga-search-manga", "title": query}

        filename = get_file_name(f"{search_url}/{query}.json", True)
        path = os.path.join(os.environ.get("TEMP_DIR", "tmp"), filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    results = json.load(f)
                    if not results:
                        raise Exception(f"No data found in the `{query}` cache in {path}")
                return results
            except Exception as e:
                logger.error(f"Failed to load `{query}` cache from {path}: {e}")

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
                results.append(
                    {
                        "url": r["url"],
                        "title": r["title"],
                        "cover_url": "",
                        "author": "",
                        "last_chapter": "",
                    }
                )

            try:
                with open(path, "w") as f:
                    json.dump(results, f)
            except Exception as e:
                logger.error(f"Error saving search results to cache: {e}")

        except Exception as e:
            logger.error(f"Error searching for manga: {e}")

        return results

    @staticmethod
    def all_domains() -> list[str]:
        return [ONEkissmanga.domain] + ONEkissmanga.alternate_domains

    @exists
    def get_info(self) -> dict:
        try:
            soup = BeautifulSoup(scraper.get(self.url).content, "html.parser")
            # Get the title
            title = soup.find(class_="post-title").text.strip()  # type: ignore

            # Get the cover URL
            cover_url = soup.find("div", class_="summary_image").find("img")["src"]  # type: ignore
            print("Cover URL: ", cover_url)

            post_contents = soup.select(".post-content_item .summary-content")
            rating_rank = post_contents[0].text.strip().split()[1]
            alternative = post_contents[2].text.strip().split(";")[0]
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

            data = {
                "url": self.url,
                "title": title,
                "alternative_title": alternative,
                "cover_url": cover_url,
                "author": authors[0],
                "artist": artists[0],
                "genre": genre,
                "tags": tags,
                "status": status,
                "description": description,
                "chapters": [ch.to_json() for ch in chapters],
                "rating": rating_rank,
                "last_updated": release,
                "total_comments": total_comments,
                "total_bookmarked": total_bookmarked,
                "type": type_,
            }

        except Exception as e:
            logger.error(f"Error getting manga info for {self.url}: {e}")
            data = {}

        return data

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
            logger.error(
                f"Error getting chapter images for {chapter_url}: {e}"
            )
            imgs = []

        return imgs


sources = [
    MangaNato,
    ONEkissmanga,
]


def all_domains() -> list[str]:
    return [domain for source in sources for domain in source.all_domains()]


def get_source(url: str) -> BaseSource:
    for source in sources:
        if source.is_valid(url):
            return source(url)
    raise SourceNotFound(
        f"Source not found for {url}\nAvailable sources: {', '.join(all_domains())}"
    )
