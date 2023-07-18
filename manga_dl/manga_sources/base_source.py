import json
from urllib.parse import urlparse
import os
from fake_headers import Headers

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.exceptions import SourceNotFound


class MangaInfo:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.cover_url = ""
        self.alternative_titles = []
        self.authors = []
        self.status = ""
        self.genres = []
        self.description = ""
        self.chapters: list = []
        self.total_chapters = 0
        self.last_chapter = ""
        self.rank = ""
        self.original_language = ""
        self.translated_language = ""
        self.artists = []
        self.last_updated = ""
        self.views = ""
        self.rating = ""
        self.tags = []
        self.type = ""
        self.total_comments = ""
        self.total_bookmarked = ""

    @classmethod
    def from_json(cls, data):
        info = cls(data["title"], data["url"])
        return info

    def to_json(self):
        return {
            "url": self.url,
            "title": self.title,
        }

    def add_to_class(self, obj):
        obj.title = self.title

    def __repr__(self):
        return f"MangaInfo(title={self.title}, url={self.url})"

    def __str__(self):
        return json.dumps(self.to_json(), indent=4)


class BaseSource:
    def __init__(self, url: str):
        self.url = url
        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self.headers: dict = Headers(headers=True).generate()
        self.use_selenium_in_get_chapter_img_urls = False

    @property
    def current_domain(self) -> str:
        return urlparse(self.url).netloc

    @staticmethod
    def get_source(url: str):
        sources = BaseSource.__subclasses__()
        for source in sources:
            if source.is_valid(url):
                return source(url)
        raise SourceNotFound(
            f"Source not found for {url}\nAvailable sources: {', '.join(BaseSource.all_domains())}"
        )

    @property
    def id(self) -> str:
        return f"base_"

    def chapter_id(self, url: str) -> str:
        if url.endswith("/"):
            return url[:-1].split("/")[-1]
        return url.split("/")[-1]

    @staticmethod
    def is_valid(url: str) -> bool:
        return any(domain in url for domain in BaseSource.all_domains())

    @staticmethod
    def valid_id(id: str) -> bool:
        return False

    @staticmethod
    def search(query: str) -> list[MangaInfo]:
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

    def get_info(self) -> MangaInfo:
        return MangaInfo("Manga Not found", "/404.html")

    def get_chapter_img_urls(self, chapter_url: str, *args, **kw) -> list[str]:
        return []


    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.url})"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def all_domains() -> list[str]:
        return []

    # in operator
    def __contains__(self, txt) -> bool:
        if "http" in txt:
            # match all domains
            return self.is_valid(txt)
        else:
            for domain in self.all_domains():
                if domain in txt or txt in domain:
                    return True

            return False
