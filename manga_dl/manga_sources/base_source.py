import json
from urllib.parse import urlparse
import os
from fake_headers import Headers

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.exceptions import SourceNotFound
from tools.utils import logger, get_app_path
from string import Formatter


class MangaInfo:
    """
    MangaInfo class

    Attributes:
        title (str): Title of the manga
        url (str): Url of the manga
        cover_url (str): Url of the cover image
        alternative_titles (list): List of alternative titles
        authors (list): List of authors
        status (str): Status of the manga
        genres (list): List of genres
        description (str): Description of the manga
        chapters (list): List of chapters
        total_chapters (int): Total chapters
        last_chapter (str): Last chapter
        rank (str): Rank of the manga
        original_language (str): Original language of the manga
        translated_language (str): Translated language of the manga
        artists (list): List of artists
        last_updated (str): Last updated date
        views (str): Total views
        rating (str): Rating of the manga
        tags (list): List of tags
        type (str): Type of the manga
        total_comments (str): Total comments
        total_bookmarked (str): Total bookmarked
    """

    def __init__(
        self,
        title: str,
        url: str,
        cover_url: str = "",
        alternative_titles: list = [],
        authors: list = [],
        status: str = "",
        genres: list = [],
        description: str = "",
        chapters: list = [],
        total_chapters: int = 0,
        last_chapter: str = "",
        rank: str = "",
        original_language: str = "",
        translated_language: str = "",
        artists: list = [],
        last_updated: str = "",
        views: str = "",
        rating: str = "",
        tags: list = [],
        type: str = "",
        total_comments: str = "",
        total_bookmarked: str = "",
    ):
        self.title = title
        self.url = url
        self.cover_url = cover_url
        self.alternative_titles = alternative_titles
        self.authors = authors
        self.status = status
        self.genres = genres
        self.description = description
        self.chapters: list = chapters
        self.total_chapters = total_chapters
        self.last_chapter = last_chapter
        self.rank = rank
        self.original_language = original_language
        self.translated_language = translated_language
        self.artists = artists
        self.last_updated = last_updated
        self.views = views
        self.rating = rating
        self.tags = tags
        self.type = type
        self.total_comments = total_comments
        self.total_bookmarked = total_bookmarked

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


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()  # type: ignore


class BaseSource:
    domain = "base.com"
    alternate_domains = []
    manga_format = "https://{domain}/manga/{ID}"

    def __init__(self, url: str):
        self.url = url
        self.temp_dir = os.environ.get("TEMP_DIR", os.path.join(get_app_path(), "tmp"))
        self.headers: dict = Headers(headers=True).generate()
        self.headers["Referer"] = f"https://{self.domain}/"
        self.use_selenium_in_get_chapter_img_urls = False

    @classmethod
    def id_to_url(cls, id: str) -> str:
        id = id.replace(f"{cls.name}_", "")
        variables = [
            fn for _, fn, _, _ in Formatter().parse(cls.manga_format) if fn is not None
        ]
        manga_format = cls.manga_format
        for var in variables:
            if "ID" in var:
                manga_format = manga_format.replace("ID", f"'{id}'")
            else:
                manga_format = manga_format.replace(var, f"cls.{var}")
        return eval("f" + repr(manga_format))

    def is_slow(self) -> bool:
        return self.use_selenium_in_get_chapter_img_urls

    @property
    def current_domain(self) -> str:
        return urlparse(self.url).netloc + f" ({'slow' if self.is_slow() else 'fast'})"

    @classproperty
    def name(cls):
        return cls.__name__.lower()  # type: ignore

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
    def _id(self) -> str:
        return self.normal_id(self.url)

    @property
    def id(self) -> str:
        return f"{self.name}_{self._id}"

    @staticmethod
    def normal_id(url: str) -> str:
        if url.endswith("/"):
            return url[:-1].split("/")[-1]
        return url.split("/")[-1]

    def chapter_id(self, url: str) -> str:
        return self.normal_id(url)

    @classmethod
    def all_domains(cls) -> list[str]:
        return [cls.domain] + cls.alternate_domains

    @classmethod
    def is_valid(cls, url: str) -> bool:
        return any(domain in url for domain in cls.all_domains())

    @classmethod
    def valid_id(cls, id: str) -> bool:
        return id.startswith(f"{cls.name}_")

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

    def get_info(self) -> MangaInfo:
        return MangaInfo("Manga Not found", "/404.html")

    def get_chapter_img_urls(self, chapter_url: str, *args, **kw) -> list[str]:
        return []

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.url})"

    def __repr__(self) -> str:
        return self.__str__()

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
