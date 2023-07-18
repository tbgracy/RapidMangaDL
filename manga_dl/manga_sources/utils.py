import os
import pprint
from typing import Any, Union
import json
import re

import sys
from urllib.parse import urlparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import get_file_name, safe_remove, logger
from cloudscraper import create_scraper
import os
import re
from .base_source import BaseSource


scraper = create_scraper(
    browser={"browser": "firefox", "platform": "windows", "mobile": False}
)


def _info_path(temp_dir, url: str) -> str:
    return os.path.join(temp_dir, f"{get_file_name(url, True)}_info.json")


# creae a check_exists decorator that will take url from the function and check if it exists in the cache
def exists(func):
    def wrapper(*args, **kwargs):
        self = args[0]
        url = self.url
        if len(args) > 1:
            url = args[1]

        if url.startswith("/"):
            url = self.url + url

        parse = urlparse(url)
        if parse.query:
            url = url.replace(parse.query, "")

        path = _info_path(self.temp_dir, url)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    if not data:
                        raise Exception(f"Error loading cache from {path}")

                    logger.info(f"Loaded info from cache: {url}: {path}")
                    if isinstance(data, dict):
                        return MangaInfo.from_json(data)
                    else:
                        return data

            except Exception as e:
                logger.error(f"Error loading info from {path}: {e}")
                safe_remove(path)
        else:
            info = False
            data = func(*args, **kwargs)
            if isinstance(data, MangaInfo):
                data = data.to_json()
                info = True

            if data:
                try:
                    with open(path, "w") as f:
                        json.dump(data, f)
                except Exception as e:
                    logger.error(f"Error saving info to {path}: {e}")
                    safe_remove(path)

            return MangaInfo.from_json(data) if info else data

    return wrapper


def static_exists(search_url):
    def decorator_warpper(func):
        def wrapper(query):
            url = f"{search_url}/{query}"
            path = _info_path(os.environ.get("TEMP_DIR", "tmp"), url)
            results = []
            data = [i.to_json() for i in func(query)]
            if sum([len(i) for i in data]) > 0:
                results = data
                try:
                    with open(path, "w") as f:
                        json.dump(data, f)
                except Exception as e:
                    logger.error(f"Error saving info to {path}: {e}")
                    safe_remove(path)
            else:
                if os.path.exists(path):
                    try:
                        with open(path, "r") as f:
                            data = json.load(f)
                            if sum([len(i) for i in data]) == 0:
                                raise Exception(f"Error loading cache from {path}")
                            else:
                                results = data
                    except Exception as e:
                        logger.error(f"Error loading info from {path}: {e}")
                        safe_remove(path)
            return [MangaInfo.from_json(result) for result in results]

        return wrapper

    return decorator_warpper


class Chapter:
    def __init__(
        self,
        url: str,
        source: Any,
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
        from . import get_source

        source = get_source(url)
        return cls(url, source)

    def __hash__(self):
        return hash(self.url)

    @property
    def id(self) -> str:
        return self.source.chapter_id(self.url)

    # eqaul operator
    def __eq__(self, other: Union["Chapter", str]) -> bool:
        url1 = self.url
        if url1.endswith("/"):
            url1 = url1[:-1]

        url2: str = other  # type: ignore
        if isinstance(other, Chapter):
            url2 = other.url

        if url2.endswith("/"):
            url2 = url2[:-1]

        return url1 == url2

    def eqal_id(self, other: Union["Chapter", str]) -> bool:
        id1 = self.id
        id2 = other.id if isinstance(other, Chapter) else self.source.chapter_id(other)
        return id1 == id2

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

    def get_chapter_imgs(self, *args, **kwargs):
        self._chapter_imgs = self.source.get_chapter_img_urls(self.url, *args, **kwargs)
        return self._chapter_imgs

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
        from . import get_source

        return cls(
            data["url"],
            get_source(data["url"]),
            data["title"],
            data["views"],
            data["date"],
        )


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
        self.chapters: list[Chapter] = []
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
        info.cover_url = data.get("cover_url", "")
        info.alternative_titles = data.get("alternative_titles", [])
        info.authors = data.get("authors", [])
        info.status = data.get("status", "")
        info.genres = data.get("genres", [])
        info.description = data.get("description", "")
        info.chapters = [
            Chapter.from_json(chapter) for chapter in data.get("chapters", [])
        ]
        info.last_chapter = data.get("last_chapter", "")
        info.rank = data.get("rank", "")
        info.original_language = data.get("original_language", "")
        info.translated_language = data.get("translated_language", "")
        info.artists = data.get("artists", [])
        info.last_updated = data.get("last_updated", "")
        info.views = data.get("views", "")
        info.rating = data.get("rating", "")
        info.tags = data.get("tags", [])
        info.type = data.get("type", "")
        info.total_comments = data.get("total_comments", "")
        info.total_bookmarked = data.get("total_bookmarked", "")
        return info

    def to_json(self):
        return {
            "url": self.url,
            "title": self.title,
            "cover_url": self.cover_url,
            "alternative_titles": self.alternative_titles,
            "authors": self.authors,
            "status": self.status,
            "genres": self.genres,
            "description": self.description,
            "chapters": [chapter.to_json() for chapter in self.chapters],
            "total_chapters": self.total_chapters,
            "last_chapter": self.last_chapter,
            "rank": self.rank,
            "original_language": self.original_language,
            "translated_language": self.translated_language,
            "artists": self.artists,
            "last_updated": self.last_updated,
            "views": self.views,
            "rating": self.rating,
            "tags": self.tags,
            "type": self.type,
            "total_comments": self.total_comments,
            "total_bookmarked": self.total_bookmarked,
        }

    @property
    def total_chapters(self):
        return len(self.chapters)

    def add_to_class(self, obj):
        obj.title = self.title
        obj.cover_url = self.cover_url
        obj.alternative_titles = self.alternative_titles
        obj.authors = self.authors
        obj.status = self.status
        obj.genres = self.genres
        obj.description = self.description
        obj.chapters = self.chapters
        obj.last_chapter = self.last_chapter
        obj.rank = self.rank
        obj.original_language = self.original_language
        obj.translated_language = self.translated_language
        obj.artists = self.artists
        obj.last_updated = self.last_updated
        obj.views = self.views
        obj.rating = self.rating
        obj.tags = self.tags
        obj.type = self.type
        obj.total_comments = self.total_comments
        obj.total_bookmarked = self.total_bookmarked

    def __repr__(self):
        return f"MangaInfo(title={self.title}, url={self.url})"

    def __str__(self):
        return json.dumps(self.to_json(), indent=4)
