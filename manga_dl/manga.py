import pprint
from typing import Union
from cloudscraper import create_scraper
from bs4 import BeautifulSoup
import concurrent.futures as cf
from ebooklib import epub
import re
import requests
import os
from fake_headers import Headers
from alive_progress import alive_bar
import shutil
from PIL import Image

Image.LOAD_TRUNCATED_IMAGES = True  # type: ignore
from tools import (
    Downloader,
    PDFChapter,
    PDF,
    create_failure_image,
    get_file_name,
    safe_remove,
    ColorFormatter,
    URLFile,
    replace_unimportant
)
import json
import logging
from fuzzywuzzy import fuzz
from tools.exceptions import MangaNotFound




os.environ["TEMP_DIR"] = "tmp"

# LOGGER_NAME, LOGGING_LEVEL, RETRY_COUNT
logger_name = os.environ.get("LOGGER_NAME", "manga")
logging_level = os.environ.get("LOGGING_LEVEL", "DEBUG")

logger = logging.getLogger(logger_name)
logger.setLevel(logging_level)

file_handler = logging.FileHandler("manga.log")
stream_handler = logging.StreamHandler()

formatter = ColorFormatter(
    "[%(levelname)s] %(asctime)s - %(message)s", datefmt="%B, %Y %I:%M %p"
)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


class Chapter:
    def __init__(self, url: str, title: str, views: str, date: str):
        self.url: str = url
        self.title: str = title
        self.views: str = views
        self.date: str = date

        self._chapter_imgs: list[str] = []
        self._img_filenames = []
        self._img_filenames_not_ordered = []
        self._qimg_filenames_not_ordered = []

        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self.check_chapter_imgs_cache_exists = True
        self.add_filenames_called = False

    @classmethod
    def from_url(cls, url: str):
        return cls(url, "", "", "")

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
    def manga_id(self):
        url = self.url
        if self.url.endswith("/"):
            url = self.url[:-1]

        return url.split("/")[-2].replace("manga-", "")

    @property
    def img_filenames(self) -> list[str]:
        if self.add_filenames_called:
            return self._img_filenames
        raise Exception("You must call add_filenames() first")

    @property
    def img_urls(self) -> list[str]:
        if not self._chapter_imgs:
            self.get_chapter_imgs()
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
        chapter_url = self.url
        url = chapter_url
        if chapter_url.endswith("/"):
            url = chapter_url[:-1]

        path = os.path.join(self.temp_dir, get_file_name(f"{url}.json", True))
        if self.check_chapter_imgs_cache_exists:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        imgs = json.load(f)
                        if not imgs:
                            raise Exception("Empty file")
                        self._chapter_imgs = imgs
                    return self._chapter_imgs
                except Exception as e:
                    logger.error(
                        f"Chapter(get_chapter_imgs)-0: Failed to get chapter imgs: {e}"
                    )
                    safe_remove(path)

        try:
            res = scraper.get(chapter_url)
            soup = BeautifulSoup(res.text, "html.parser")
            imgs = soup.select(".container-chapter-reader img")  # type: ignore
            imgs = [i.get("src") for i in imgs]  # type: ignore
            imgs = [i for i in imgs if self.manga_id in i]  # type: ignore

            with open(path, "w") as f:
                json.dump(imgs, f)

            self._chapter_imgs = imgs  # type: ignore

        except Exception as e:
            logger.error(
                f"Chapter(get_chapter_imgs)-1: Failed to get chapter imgs: {e}"
            )

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
        }

    @classmethod
    def from_json(cls, json: dict):
        return cls(json["url"], json["title"], json["views"], json["date"])


class Manga:
    def __init__(self, url: str):
        self.url = url
        self.id = self.get_id()

        self.title = ""
        self.cover_url = ""
        self.alternative_title = ""
        self.author = ""
        self.status = ""
        self.genre = ""
        self.description = ""
        self.chapters: list[Chapter] = []
        self.total_chapters = 0
        self.last_chapter = 0
        self.updated = ""
        self.views = ""
        self.rating = ""
        self.retry_count = int(os.environ.get("RETRY_COUNT", "3"))

        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.headers: dict = Headers().generate()
        self.headers.update({"Referer": "https://chapmanganato.com/"})

        self._info_set = False
        self._save_chapters_str = ""
        self._pbar = None
        self._quality = 100
        # self._manager = FileManager()

        self.check_temp_dir()

    @classmethod
    def search(cls, query: str) -> list["Manga"]:
        if "http" in query:
            m = cls(query)
            m.set_info()
            return [m]

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

        try:
            res = requests.post(url, headers=headers, data=data)
            res.raise_for_status()
            result = res.json()
            try:
                with open(path, "w") as f:
                    json.dump(result, f)
            except Exception as e:
                logger.error(f"Manga(search)-0: Failed to save search result: {e}")

        except Exception as e:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        result = json.load(f)
                except Exception as e:
                    logger.error(f"Manga(search)-1: Failed to load search result: {e}")
                    os.remove(path)
                    result = {"searchlist": []}
            else:
                logger.error(f"Manga(search)-2: Failed to get search result: {e}")
                result = {"searchlist": []}

        mangas = []
        for d in result["searchlist"]:
            mangas.append(Manga.from_search(d))
        return mangas

    @classmethod
    def from_search(cls, json: dict) -> "Manga":
        url = json["url_story"]
        c = cls(url)
        title = json["name"]
        title = re.sub(r"<[^>]*>", "", title)
        title = title.strip()
        title = title.upper()
        c.title = title
        c.cover_url = json["image"]
        c.author = json["author"]
        c.last_chapter = json["lastchapter"]
        return c

    @classmethod
    def from_json(cls, json: dict) -> "Manga":
        c = cls(json["url"])
        c.title = json["title"]
        c.cover_url = json["cover_url"]
        c.author = json["author"]
        c.alternative_title = json["alternative_title"]
        c.status = json["status"]
        c.genre = json["genre"]
        c.description = json["description"]
        c.chapters = [Chapter.from_json(chapter) for chapter in json["chapters"]]
        c.total_chapters = json["total_chapters"]
        c.last_chapter = json["last_chapter"]
        c.updated = json["updated"]
        c.views = json["views"]
        c.rating = json["rating"]
        return c

    @classmethod
    def from_id(cls, id: str) -> "Manga":
        url = f"https://chapmanganato.com/manga-{id}"
        return cls(url)

    @classmethod
    def autodetect(cls, inp) -> "Manga":
        if isinstance(inp, str):
            if "http" in inp:
                return cls(inp)
            elif "manga-" in inp:
                return cls.from_id(inp)
            elif inp[2:].isdigit():
                return cls.from_id(f"manga-{inp}")
            else:
                most_likely = None
                mangas = Manga.search(inp)
                # find most likely with title with fuzz
                ratio = 0
                for manga in mangas:
                    r = fuzz.ratio(inp, manga.title)
                    if r > ratio:
                        ratio = r
                        most_likely = manga
                if not most_likely:
                    raise MangaNotFound(f"Could not find manga with title: {inp}")
                return most_likely

        elif isinstance(inp, Manga):
            return inp
        elif isinstance(inp, dict):
            return cls.from_json(inp)
        elif isinstance(inp, list):
            return cls.from_json(inp[0])
        elif isinstance(inp, int):
            return cls.from_id(f"manga-{inp}")
        else:
            raise MangaNotFound(f"Could not find manga with: {inp}")

    def to_json(self) -> dict:
        return {
            "url": self.url,
            "id": self.id,
            "title": self.title,
            "cover_url": self.cover_url,
            "author": self.author,
            "alternative_title": self.alternative_title,
            "status": self.status,
            "genre": self.genre,
            "description": self.description,
            "total_chapters": self.total_chapters,
            "last_chapter": self.last_chapter,
            "updated": self.updated,
            "views": self.views,
            "rating": self.rating,
            "chapters": self.chapters,
        }

    def __str__(self) -> str:
        return pprint.pformat(self.to_json())

    def __repr__(self) -> str:
        return f"Manga({self.url})"

    def get_css(self) -> str:
        return """@namespace epub "http://www.idpf.org/2007/ops";
            * {
                margin: 0;
                padding: 0;
            }

            body {
                font-family: Cambria, Liberation Serif, Bitstream Vera Serif, Georgia, Times, Times New Roman, serif;
            }

            h2 {
                text-align: left;
                text-transform: uppercase;
                font-weight: 200;
                font-style: italic;
                color: #888;
            }
            p {
                text-align: justify;
            }

            ol {
                list-style-type: none;
            }
            ol > li:first-child {
                margin-top: 0.3em;
            }
            nav[epub|type~='toc'] > ol > li > ol  {
                list-style-type:square;
            }
            nav[epub|type~='toc'] > ol > li > ol > li {
                margin-top: 0.3em;
            }  """

    def get_id(self) -> str:
        if self.url[-1] == "/":
            self.url = self.url[:-1]
        return self.url.split("/")[-1].replace("manga-", "")

    def get_save_name(self) -> str:
        if self._quality == None:
            quality = 100
        else:
            quality = self._quality

        title = f"{self.title}_quality_{quality}_chapters_{self._save_chapters_str}"
        pat = r"[^a-zA-Z0-9]"
        return re.sub(pat, "_", title)

    def set_info(self, force: bool = False):
        if self._info_set and not force and len(self.chapters) == self.total_chapters:
            return

        path = os.path.join(self.temp_dir, f"{get_file_name(self.url, True)}_info.json")
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                self.title = data["title"]
                self.cover_url = data["cover_url"]
                self.alternative_title = data["alternative_title"]
                self.author = data["author"]
                self.status = data["status"]
                self.genre = data["genre"]
                self.description = data["description"]
                self.chapters = [
                    Chapter.from_json(chapter) for chapter in data["chapters"]
                ]
                self.total_chapters = data["total_chapters"]
                self._info_set = True
                return
        except Exception as e:
            logger.error(f"Error loading info from {path}")

            data = get_manga_info(url)
        

            self.alternative_title = alt
            self.title = title
            self.author = author
            self.status = status
            self.genre = genre
            self.description = description
            self.chapters = chapters
            self.total_chapters:int = len(chapters)
            self.cover_url = cover_url
            self.updated = updated
            self.views = views
            self.rating = rating

            info = {
                "url": self.url,
                "title": self.title,
                "alternative_title": self.alternative_title,
                "author": self.author,
                "status": self.status,
                "genre": self.genre,
                "description": self.description,
                "total_chapters": self.total_chapters,
                "cover_url": self.cover_url,
                "updated": self.updated,
                "views": self.views,
                "rating": self.rating,
                "chapters": [c.to_json() for c in self.chapters],
            }

            try:
                with open(path, "w") as f:
                    json.dump(info, f, indent=4)
                self._info_set = True
            except Exception as e:
                logger.error(f"Failed to save {self.id}.json", exc_info=True)
                if os.path.exists(path):
                    os.remove(path)
        except Exception as e:
            logger.error(f"Error setting info for {self.url}", exc_info=True)
            raise MangaNotFound(f"Could not find manga with url {self.url}")

    def chapter_template(self, chapter_title, filenames) -> str:
        return f"""<h1>{chapter_title}</h1>
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center">
        {''.join([f'<img src="images/{i}" alt="{i}" style="width: 100%; height: auto; margin:0px; padding: 0px; border:0px" />' for i in filenames])}
           </div>
        """

    def check_temp_dir(self):
        if not os.path.exists(self.temp_dir):
            os.mkdir(self.temp_dir)

    def download_cover(self):
        path = os.path.join(self.temp_dir, get_file_name(self.cover_url))
        if os.path.exists(path):
            return path
        res = requests.get(self.cover_url, headers=self.headers)
        with open(path, "wb") as f:
            f.write(res.content)
        return path

    def chapters_exists(
        self, inputs, chapters: list[Chapter]) -> dict[Union[str, int], list[Chapter]]:
        if isinstance(inputs, str):
            inputs = [inputs]
        
        chapter_url_dict = {i.url: i for i in chapters}
        chapters_title_dict = {i.title: i for i in chapters}
        selected_chapters = {}
        for i in inputs:
            if not i:
                selected_chapters[i] = []
            
            if isinstance(i, str):
                if "http" in i:
                    if i in chapter_url_dict:
                        selected_chapters[i] = [chapter_url_dict[i]]
                elif i.isdigit():
                    int_i = int(i)
                    if int_i < len(chapters):
                        selected_chapters[str(i)] = [chapters[int_i]]
                        
                elif "," in i:
                    ii = replace_unimportant(i, but=["-",","])
                    vals = [a.strip() for a in ii.split(",")]
                    schapters = self.chapters_exists(vals, chapters)
                    selected_chapters[i] = [i for a in schapters.values() for i in a]
                    
                elif "-" in i:
                    ii = replace_unimportant(i, but=["-",","])
                    vals = [i.strip() for i in ii.split("-")]
                    schapters = self.chapters_exists(vals, chapters)
                    ct1 = chapters.count(schapters[vals[0]][0])
                    start_index = 0
                    if ct1 > 0:
                        start_index = chapters.index(schapters[vals[0]][0])
                    ct2 = chapters.count(schapters[vals[1]][0])
                    end_index = self.total_chapters - 1
                    if ct2 > 0:
                        end_index = chapters.index(schapters[vals[1]][0])
                        
                    selected_chapters[i] = chapters[start_index:end_index]
                    
                elif i == "all":
                    selected_chapters[i] = chapters
                    
                else:
                    if i in chapters_title_dict:
                        selected_chapters[i] = [chapters_title_dict[i]]
                        
            elif isinstance(i, int):
                if i < len(chapters):
                    selected_chapters[i] = [chapters[i]]
            
            
            elif isinstance(i, Chapter):
                selected_chapters[i] = [i]

        return selected_chapters

    def select_chapters(self, selected: Union[str,int,Chapter,None], exclude: Union[str,int,Chapter,None] = None): 
        self.set_info()
        
        selected_chapters = self.chapters_exists(selected, self.chapters)
        chapters = []
        for i in selected_chapters.values():
            chapters.extend(i)
            
        if exclude:
            selected_excluded_chapters = self.chapters_exists(exclude, self.chapters)
            excluded_chapters = []
            for i in selected_excluded_chapters.values():
                excluded_chapters.extend(i)
            chapters = [i for i in chapters if i not in excluded_chapters]
        
        chapters_url_dict = {i.url: [0,i] for i in chapters}
        for i in chapters:
            chapters_url_dict[i.url][0] += 1
        
        self.chapters = []
        for i in chapters_url_dict.values():
            if i[0] > 0:
                self.chapters.append(i[1])
        
        self._save_chapters_str = f"selected_{selected}_exclude_{exclude}"
        
        logger.info(f"Selected {len(self.chapters)} chapters")
        return self.chapters
            
        

    def lower_quality(self, filename: str, quality: int):
        # add quality to filename
        qfilename = filename.split(".")
        qfilename[-2] += f"_{quality}"
        qfilename = ".".join(qfilename)
        qpath = os.path.join(self.temp_dir, qfilename)
        path = os.path.join(self.temp_dir, filename)

        if os.path.exists(qpath):
            return filename, qfilename

        try:
            img = Image.open(path)

            img.convert("RGB").save(qpath, optimize=True, quality=quality)
            img.close()
        except Exception as e:
            logger.error(f"Manga(lower_quality): Error lowering quality: {e}")
            logger.info(f"Manga(lower_quality): Saving image without lowering quality")
            shutil.copy(path, qpath)

        return filename, qfilename

    def create_failure_image(self, url):
        filename = get_file_name(f"{url}-error.png", True)
        create_failure_image("error.png", os.path.join(self.temp_dir, filename), url)
        return filename

    def check_img(self, file):
        _, filename = file
        path = os.path.join(self.temp_dir, filename)
        try:
            Image.open(path).close()
            return True, file
        except Exception as e:
            logger.error(f"Manga(check_img): Failed to open {path}", exc_info=True)
            return False, file

    def check_imgs(self, files):
        success = []
        failure = []
        with cf.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.check_img, file) for file in files]
            with alive_bar(len(futures), title="Checking images") as bar:
                for future in cf.as_completed(futures):
                    success_, file = future.result()
                    if success_:
                        success.append(file)
                    else:
                        failure.append(file)
                    bar()
        return success, failure

    def remove_files(self, filenames):
        for filename in filenames:
            path = os.path.join(self.temp_dir, filename)
            if os.path.exists(path):
                os.remove(path)

    def add_chapters(
        self, book: Union[epub.EpubBook, PDF], quality=None
    ) -> Union[list[epub.EpubHtml], list[PDFChapter]]:
        if quality == 100:
            quality = None

        with cf.ThreadPoolExecutor() as executor:
            futures = [executor.submit(i.get_chapter_imgs) for i in self.chapters]
            with alive_bar(len(futures), title="Getting chapters") as bar:
                for future in cf.as_completed(futures):
                    bar()

        img_urls = []
        img_url_to_chapter: dict[str, Chapter] = {}
        for chapter in self.chapters:
            chapter_imgs = chapter.img_urls
            img_urls.extend(chapter_imgs)
            for img_url in chapter_imgs:
                img_url_to_chapter[img_url] = chapter

        iurls = img_urls
        checked_files = []
        for i in range(self.retry_count):
            if not iurls:
                break

            with Downloader(iurls, self.headers, self.temp_dir) as downloader:
                downloaded_files, failed_urls = downloader.download()

            downloaded_files, failed_files = self.check_imgs(downloaded_files)

            self.remove_files([i[1] for i in failed_files])

            checked_files.extend(downloaded_files)
            iurls = [i[0] for i in failed_files] + failed_urls

        failed_files = [
            URLFile(i, os.path.join(self.temp_dir, self.create_failure_image(i)))
            for i in iurls
        ]

        all_files: list[URLFile] = checked_files + failed_files

        for img_url, dlfile in all_files:
            img_url_to_chapter[img_url].add_file((img_url, dlfile))

        for chapter in self.chapters:
            chapter.order_files()

        img_filenames_chapter = {}
        for chapter in self.chapters:
            for filename in chapter.img_filenames:
                img_filenames_chapter[filename] = chapter

        if quality is not None:
            with cf.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self.lower_quality, i, quality)
                    for i in img_filenames_chapter.keys()
                ]
                with alive_bar(
                    len(futures), title=f"Lowering quality to {quality}"
                ) as bar:
                    for future in cf.as_completed(futures):
                        filename, qfilename = future.result()
                        chapter = img_filenames_chapter[filename]
                        chapter.add_qfile((filename, qfilename))
                        bar()

            for chapter in self.chapters:
                chapter.order_qfiles()

        items = []
        for chapter in self.chapters:
            title = chapter.title
            filenames = chapter.img_filenames
            if isinstance(book, epub.EpubBook):
                epub_chapter = epub.EpubHtml(
                    title=title, file_name=f"{title}.xhtml", lang="en"
                )

                epub_chapter.content = self.chapter_template(title, filenames)
                book.add_item(epub_chapter)
                items.append(epub_chapter)

                for filename in filenames:
                    path = os.path.join(self.temp_dir, filename)
                    with open(path, "rb") as f:
                        book.add_item(
                            epub.EpubItem(
                                uid=f"image_{filename}",
                                file_name=f"images/{filename}",
                                media_type="image/jpeg",
                                content=f.read(),
                            )
                        )

            elif isinstance(book, PDF):
                paths = [os.path.join(self.temp_dir, i) for i in filenames]
                items.append((title, paths))

        if isinstance(book, PDF):

            def create_chapter(item):
                title, paths = item
                return book.create_chapter(title, paths)

            nitems = items.copy()
            items = []
            with alive_bar(total=len(items), title="Creating PDF chapters") as bar:
                with cf.ThreadPoolExecutor() as executor:
                    for item in executor.map(create_chapter, nitems):
                        items.append(item)
                        bar()

        return items

    def create_epub(self, quality=None, path:str=""): 
        book = epub.EpubBook()

        self._quality = quality
        chapters = self.add_chapters(book, quality=quality)

        # set metadata
        book.set_identifier(self.id)
        book.set_title(self.title)
        book.set_language("en")

        book.add_author(self.author)

        # add cover image
        cover_path = self.download_cover()
        with open(cover_path, "rb") as f:
            book.set_cover("cover.jpg", f.read())

        about = epub.EpubHtml(title="Introduction", file_name="about.xhtml", lang="en")
        about.content = f"<h2>{self.title} ({self.alternative_title})</h2><h3>Author: {self.author}</h3><h3>Source: {self.url}</h3><h3>Status: {self.status}</h3><h3>Genres: {self.genre}</h3><h3>Select Chapter {self._save_chapters_str}</h3><h3>Description:</h3><p>{self.description}</p>"
        book.add_item(about)

        book.toc = tuple([about] + list(chapters))  # type: ignore

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self.get_css().encode("utf-8"),
        )

        book.add_item(nav_css)

        book.spine = ["cover", "nav", about] + list(chapters)

        filename = f"{self.get_save_name()}.epub"
        if path is None:
            path = filename
        else:
            if not os.path.isdir(path):
                os.makedirs(path)
            path = os.path.join(path, filename)
        
        logger.info(f"Manga(create_epub): Saving to {path}")
        epub.write_epub(path, book)
        return path

    def create_pdf(self, quality=None, path:str=""): # type: ignore
        pdf = PDF()

        self._quality = quality
        pdf.set_title(self.title)
        pdf.set_author(self.author)
        pdf.set_cover(self.download_cover())

        chapters: list[PDFChapter] = self.add_chapters(pdf, quality=quality)  # type: ignore
        [pdf.add_chapter(i) for i in chapters]

        pdf.set_toc(chapters)


        data = [
            {
                "label": "Title",
                "value": f"{self.title} ({self.alternative_title})",
            },
            {
                "label": "Status",
                "value": self.status,
            },
            {
                "label": "Author",
                "value": self.author,
            },
            {
                "label": "Genres",
                "value": self.genre,
            },
            {
                "label": "Select Chapter",
                "value": self._save_chapters_str,
            },
            {
                "label": "Description",
                "value": self.description,
            },
        ]

        pdf.set_page_data(data)

        filename = f"{self.get_save_name()}.pdf"
        
        if path is None:
            path = filename
        else:
            if not os.path.isdir(path):
                os.makedirs(path)
                
            path = os.path.join(path, filename)
            
        pdf.write(path)
        logger.info(f"Manga(create_pdf): Saving to {path}")

        return path


__all__ = ["Manga", "Chapter", "MangaNotFound"]



    
