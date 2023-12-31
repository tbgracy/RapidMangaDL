import nest_asyncio

nest_asyncio.apply()

import pprint
from typing import Union
import concurrent.futures as cf
from ebooklib import epub
import re
import requests
import os
import shutil
import sys

from PIL import Image
from fuzzywuzzy import fuzz

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools import (
    Downloader,
    PDFChapter,
    PDF,
    create_failure_image,
    get_file_name,
    URLFile,
    logger,
    tqdm,
    driver_manager as manager,
    get_app_path,
    share_progress_bar,
)

from tools.exceptions import MangaNotFound

from manga_sources import Chapter, MangaInfo, BaseSource, get_source, sources


app_path = get_app_path()
temp_dir = os.path.join(app_path, "tmp")
os.environ["TEMP_DIR"] = os.environ.get("TEMP_DIR", temp_dir)
temp_dir = os.environ["TEMP_DIR"]
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()  # type: ignore


class Manga:
    """
    Manga

    Atributes:
    ----------
    url: str -> url of the manga
    source: Source -> Source object (see)
    id: str -> id of the manga
    title: str -> title of the manga
    cover_url: str -> url of the cover image
    alternative_title: str -> alternative title of the manga

    >>> manga = Manga("https://manganelo.com/manga/ta918772")
    >>> manga.set_info() # set manga info
    >>> manga.title
    """

    def __init__(self, url: str):  # type: ignore
        self.url = url

        self.source: BaseSource = get_source(url)
        self.id = self.source.id

        self.title = ""
        self.cover_url = ""
        self.alternative_titles = []
        self.authors = []
        self.status = ""
        self.genres = []
        self.description = ""
        self.chapters: list[Chapter] = []
        self.last_chapter = ""
        self.last_updated = ""
        self.rank = ""
        self.original_language = ""
        self.translated_language = ""
        self.artists = []
        self.views = ""
        self.rating = ""
        self.retry_count = int(os.environ.get("RETRY_COUNT", "3"))

        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.headers = self.source.headers

        self._info_set = False
        self._save_chapters_str = ""
        self._pbar = None
        self._quality = 100
        # self._manager = FileManager()

        self.check_temp_dir()

    @staticmethod
    def clear_cache():
        """
        Clears all cache
        """

        temp_dir = os.environ.get("TEMP_DIR", "tmp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

    @classproperty
    def cache_path(cls):
        return os.path.abspath(os.environ.get("TEMP_DIR", "tmp"))
    
    @classproperty
    def save_path(cls):
        return os.path.join(get_app_path(), "Downloads")
    
    

    @property
    def genre(self) -> str:
        return ", ".join(self.genres)

    @property
    def artist(self) -> str:
        return ", ".join(self.artists)

    @property
    def alternative_title(self) -> str:
        return ", ".join(self.alternative_titles)

    @property
    def author(self) -> str:
        return ", ".join(self.authors)

    @property
    def updated(self) -> str:
        return self.last_updated

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @staticmethod
    def search(query: str) -> list["Manga"]:
        """
        Search for manga in all sources

        Parameters:
        -----------
        query: str -> query to search for

        Returns:
        --------
        list[Manga] -> list of Manga objects
        """

        mangas = []
        with cf.ThreadPoolExecutor() as executor:
            futures = [executor.submit(source.search, query) for source in sources]
            for future in cf.as_completed(futures):
                results = future.result()
                mangas.extend(results)

        mangas = [Manga.from_mangainfo(manga) for manga in mangas]
        mangas.sort(
            key=lambda x: fuzz.ratio(x.title.lower(), query.lower()), reverse=True
        )

        return mangas

    @classmethod
    def from_json(cls, data: dict) -> "Manga":
        m = cls(data["url"])
        manga = MangaInfo(data["url"], data["title"])
        manga.from_json(data)
        manga.add_to_class(m)
        return m

    @classmethod
    def from_mangainfo(cls, manga: MangaInfo) -> "Manga":
        m = cls(manga.url)
        manga.add_to_class(m)
        return m

    @classmethod
    def from_id(cls, id: str) -> "Manga":
        for s in sources:
            if s.valid_id(id):
                return cls(s.id_to_url(id))
        raise MangaNotFound(f"Could not find manga with id: {id}")

    @classmethod
    def autodetect(cls, inp, source: str = "") -> "Manga":
        if isinstance(inp, str):
            if "http" in inp:
                manga = cls(inp)
                manga.set_info()
                return manga
            else:
                most_likely = None
                mangas = Manga.search(inp)
                # find most likely with title with fuzz
                ratio = 0
                for manga in mangas:
                    if source:
                        if source not in manga.source:
                            continue

                    r = fuzz.token_set_ratio(manga.title.upper(), inp.upper())
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
            "domain": self.source.current_domain,
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

    def get_save_name(self) -> str:
        if self._quality == None:
            quality = 100
        else:
            quality = self._quality

        title = f"{self.title}_quality_{quality}_chapters_{self._save_chapters_str}_source_{self.source.current_domain}"
        pat = r"[^a-zA-Z0-9-_]"
        return re.sub(pat, "_", title)

    def set_info(self):
        m = self.source.get_info()
        m.add_to_class(self)

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

    def chapters_exists(self, *querys, chapters: list[Chapter], merger="and"):
        """
        Checks if the given inputs are valid chapters

        Parameters
        ----------
        querys : Union[str, int, list[str], list[int]]
            The inputs to check
        chapters : list[Chapter]
            The chapters to check against
        merger: str
            Merge On

        Returns
        -------
            list[Chapter]

        Examples
        --------
            >>> chapters_exists("1", manga.chapters)
            >>> chapters_exists(["1", "2"], manga.chapters)
        """

        text = "  "
        merger = merger.lower()[0]
        for i, query in enumerate(querys):
            if isinstance(query, list):
                if len(query) == 2:
                    if merger == "r":
                        text += f"{query[0]-query[1]},"
                        continue
                text += ",".join([str(i) for i in query])
                text += ","

            elif isinstance(query, str) or isinstance(query, int):
                query = str(query)
                if merger == "r":
                    flag = False
                    if text[-1] != "-":
                        flag = True
                    if "http" in query:
                        if "-http" in query:
                            flag = False
                    elif "-" in query:
                        flag = False

                    if flag:
                        text += f"{query}-"
                        continue

                text += f"{query},"

        text = text.strip()
        if text[-1] == "-" or text[-1] == ",":
            text = text[:-1]

        
        exps = [x.strip() for x in text.split(",")]
        inputs = [x.replace(" ", "") for x in exps if x]

        int_range = re.compile(r"(\d+)-(\d+)")
        id_range_exists = re.compile(r"-ID_")
        http_range_exists = re.compile(r"-https?://")
        last_pat = re.compile(r"(last|latest)(\d+)?")

        # singels
        int_single = re.compile(r"\d+")
        id_single = re.compile(r"ID_([\w-]+)")
        http_single = re.compile(r"https://[\w-]+")

        url_dict = {x.url: i for i, x in enumerate(chapters)}
        id_dict = {x.id: i for i, x in enumerate(chapters)}

        matches = []
        for inp in inputs:
            irm = int_range.match(inp)
            if irm:
                start = int(irm.group(1)) - 1
                end = int(irm.group(2)) - 1

                if start < 0 or end < 0:
                    logger.error("Invalid range", inp)
                    continue
                if start > end:
                    logger.error("Invalid range", inp)
                    continue
                if end >= len(chapters):
                    logger.error("Invalid range", inp)

                matches.extend(chapters[start : end + 1])
                continue

            idm = id_range_exists.search(inp)
            if idm:
                parts = inp.split("-ID_")
                if len(parts) == 2:
                    s = parts[0].replace("ID_", "")
                    e = parts[1]
                    if s in id_dict and e in id_dict:
                        start = id_dict[s]
                        end = id_dict[e]
                        matches.extend(chapters[start : end + 1])
                    else:
                        logger.error(f"ID not found: {s} or {e}")
                else:
                    logger.error(f"Invalid ID Range: {inp}")
                continue

            httpm = http_range_exists.search(inp)
            if httpm:
                parts = inp.split("-http")
                if len(parts) == 2:
                    s = parts[0]
                    e = "http" + parts[1]
                    if s in url_dict and e in url_dict:
                        start = url_dict[s]
                        end = url_dict[e]
                        matches.extend(chapters[start : end + 1])
                    else:
                        logger.error(f"URL not found: {s} or {e}")
                else:
                    logger.error(f"Invalid URL Range: {inp}")
                continue

            lastm = last_pat.match(inp)
            if lastm:
                end = int(lastm.group(2)) if lastm.group(2) else 5
                matches.extend(chapters[-end:])
                continue

            ism = int_single.match(inp)
            if ism:
                start = int(ism.group(0)) - 1
                end = start

                if start < 0:
                    logger.error("Invalid chapter", inp)
                    continue
                if start >= len(chapters):
                    logger.error("Invalid chapter", inp)
                    continue

                matches.append(chapters[start])

                continue

            idsm = id_single.match(inp)
            if idsm:
                s = idsm.group(1)
                if s in id_dict:
                    start = id_dict[s]
                    end = start
                    matches.append(chapters[start])
                else:
                    logger.error(f"Invalid ID: {s}")
                continue

            httpm = http_single.match(inp)
            if httpm:
                s = httpm.group(0)
                if s in url_dict:
                    start = url_dict[s]
                    end = start
                    matches.append(chapters[start])
                else:
                    logger.error(f"Invalid URL: {s}")
                continue

        if matches:
            return matches
        else:
            return []

    def _get_save_chapters_str(self, selected_chapters: list[Chapter]):
        # if len is less than 4 then just indexs else range and total chapters
        if len(selected_chapters) < 4:
            return ",".join([i.short_name for i in selected_chapters])
        else:
            return f"{selected_chapters[0].short_name}-{selected_chapters[-1].short_name}_total_{len(selected_chapters)}"

    def select_chapters(
        self,
        selected: Union[str, int, Chapter, None, list[Union[str, int, Chapter]]],
        exclude: Union[str, int, Chapter, None, list[Union[str, int, Chapter]]] = None,
        smerge="and",
        emerge="and",
    ):
        """
        Selects the chapters to download

        Parameters
        ----------
        selected : Union[str, int, Chapter, None] The chapters to download
        exclude : Union[str, int, Chapter, None], optional The chapters to exclude

        Examples
        --------
            >>> manga.select_chapters("1")
            >>> manga.select_chapters(["1", "2"])
            >>> manga.select_chapters("1-5")
            >>> manga.select_chapters("1,2,3")
            >>> manga.select_chapters("1,2,3-5", exclude="4")
            >>> manga.select_chapters("1,2,3-5", exclude="4,5")
            >>> manga.select_chapters("https://manganato.com/manga-aa123456/chapter-1-https://manganato.com/manga-aa123456/chapter-2")
        """

        self.set_info()
        if isinstance(selected, list):
            if isinstance(selected[0], Chapter):
                self.chapters = selected  # type: ignore
                logger.info(f"Selected {len(self.chapters)} chapters")
                self._save_chapters_str = (
                    f"{self._get_save_chapters_str(self.chapters)}"  # type: ignore
                )
                return self.chapters

        chapters = self.chapters_exists(selected, chapters=self.chapters, merger=smerge)

        if exclude:
            selected_excluded_chapters = self.chapters_exists(
                exclude, chapters=self.chapters, merger=emerge
            )
            chapters = [i for i in chapters if i not in selected_excluded_chapters]

        chapters_dict = {i.id: i for i in self.chapters}
        chapters = [chapters_dict[i.id] for i in chapters]
        self.chapters = chapters
        
        self._save_chapters_str = f"{self._get_save_chapters_str(self.chapters)}"

        logger.info(f"Selected {len(self.chapters)} chapters")
        return self.chapters

    def lower_quality(self, filename: str, quality: int):
        # add quality to filename
        name, ext = os.path.splitext(filename)
        name = f"{name}_q{quality}"
        qfilename = f"{name}{ext}"

        qpath = os.path.join(self.temp_dir, qfilename)
        path = os.path.join(self.temp_dir, filename)

        if os.path.exists(qpath):
            return filename, qfilename

        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")

            img.save(qpath, optimize=True, quality=quality)
            img.close()
        except Exception as e:
            logger.error(f"Error lowering quality: {e}")
            logger.info(f"Saving image without lowering quality")
            shutil.copy(path, qpath)

        return filename, qfilename

    def create_failure_image(self, url):
        filename = get_file_name(f"{url}-error.png", True)
        create_failure_image(os.path.join(self.temp_dir, filename), url)
        return filename

    def check_img(self, file):
        _, filename = file
        path = os.path.join(self.temp_dir, filename)
        try:
            Image.open(path).close()
            return True, file
        except Exception as e:
            logger.error(f"Manga(check_img): Failed to open {path}: {e}")
            return False, file

    def check_imgs(self, files):
        success = []
        failure = []
        with cf.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.check_img, file) for file in files]
            with tqdm(total=len(futures), desc="Checking images") as bar:
                for future in cf.as_completed(futures):
                    success_, file = future.result()
                    if success_:
                        success.append(file)
                    else:
                        failure.append(file)
                    bar.update(1)
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

        if not self.source.use_selenium_in_get_chapter_img_urls:
            with cf.ThreadPoolExecutor() as executor:
                futures = [executor.submit(i.get_chapter_imgs) for i in self.chapters]
                with tqdm(total=len(futures), desc="Getting Chapter Imgs") as bar:
                    for future in cf.as_completed(futures):
                        bar.update(1)
                        share_progress_bar(len(self.chapters), bar.n, bar.desc)

        else:
            if not manager.chromedriver_installed:
                logger.error(
                    f"You need chrome to download for {self.source.current_domain}"
                )
                logger.error("Please install chrome and try again")
                sys.exit(1)

            logger.info(
                "Using Selenium to get chapter img urls (this may take a while)"
            )

            driver = manager.get_driver()
            i = 0
            for chapter in tqdm(self.chapters, desc="Getting Chapter Imgs"):
                chapter.get_chapter_imgs(driver=driver[1])
                share_progress_bar(len(self.chapters), i, "Getting Chapter Imgs")
                i += 1
            manager.release_driver(driver[0])
            manager.quit()

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

            if i > 0:
                logger.info(f"Retrying failed images: {len(iurls)}")
                share_progress_bar(len(iurls), 0, "Retrying failed images")

            with Downloader(iurls, self.headers, self.temp_dir) as downloader:
                downloaded_files, failed_urls = downloader.download()

            if downloaded_files:
                downloaded_files, failed_files = self.check_imgs(downloaded_files)
                self.remove_files([i[1] for i in failed_files])
                checked_files.extend(downloaded_files)

                iurls = [i[0] for i in failed_files] + failed_urls

            else:
                iurls = failed_urls

        if iurls:
            logger.error(f"Total failed images: {len(iurls)}. Try again later")
            logger.info("Continuing with failed images")


        failed_files = []
        with cf.ThreadPoolExecutor() as executor:
            for result in executor.map(self.create_failure_image, iurls):
                failed_files.append(result)


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
                with tqdm(
                    total=len(futures), desc=f"Lowering quality to {quality}"
                ) as bar:
                    for future in cf.as_completed(futures):
                        filename, qfilename = future.result()
                        chapter = img_filenames_chapter[filename]
                        chapter.add_qfile((filename, qfilename))
                        bar.update(1)
                        share_progress_bar(len(futures), bar.n, bar.desc)

            for chapter in self.chapters:
                chapter.order_qfiles()

        items = []
        for chapter in self.chapters:
            title = chapter.title
            ch_id = chapter.id
            filenames = chapter.img_filenames
            if isinstance(book, epub.EpubBook):
                epub_chapter = epub.EpubHtml(
                    title=title, file_name=f"{ch_id}.xhtml", lang="en"
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
            with tqdm(total=len(items), desc="Creating PDF chapters") as bar:
                with cf.ThreadPoolExecutor() as executor:
                    for item in executor.map(create_chapter, nitems):
                        items.append(item)
                        bar.update(1)
                        share_progress_bar(len(nitems), bar.n, bar.desc)

        return items

    def get_save_path(self, path: str = "") -> str:
        if not path:
            path = os.path.join(get_app_path(), "Downloads")
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def create_epub(self, quality=None, path: str = ""):
        """
        Create an epub file of the novel.

        Parameters
        ----------
        quality : int, optional
            The quality of the images in the epub file. If None, the original quality is used. Defaults to None.
        path : str, optional
            The path to save the epub file to. If None, the file is saved to the current working directory. Defaults to current working directory.

        """

        book = epub.EpubBook()

        self._quality = quality
        chapters = self.add_chapters(book, quality=quality)

        share_progress_bar(3, 0, "Creating Epub")

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

        share_progress_bar(3, 2, "Creating Epub")

        book.spine = ["cover", "nav", about] + list(chapters)

        filename = f"{self.get_save_name()}.epub"
        path = self.get_save_path(path)
        path = os.path.join(path, filename)

        logger.info(f"Manga(create_epub): Saving to {path}")
        epub.write_epub(path, book)
        share_progress_bar(3, 3, "Creating Epub")
        return path

    def create_pdf(self, quality=None, path: str = ""):  # type: ignore
        """
        Create a pdf file of the novel.

        Parameters
        ----------
        quality : int, optional
            The quality of the images in the pdf file. If None, the original quality is used. Defaults to None.
        path : str, optional
            The path to save the pdf file to. If None, the file is saved to the current working directory. Defaults to current working directory.
        """

        pdf = PDF()

        self._quality = quality
        pdf.set_title(self.title)
        pdf.set_author(self.author)
        pdf.set_cover(self.download_cover())

        chapters: list[PDFChapter] = self.add_chapters(pdf, quality=quality)  # type: ignore
        share_progress_bar(3, 0, "Creating PDF")
        [pdf.add_chapter(i) for i in chapters]

        pdf.set_toc(chapters)

        share_progress_bar(3, 2, "Creating PDF")
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
        path = self.get_save_path(path)
        path = os.path.join(path, filename)

        pdf.write(path)
        logger.info(f"Manga(create_pdf): Saving to {path}")
        share_progress_bar(3, 3, "Creating PDF")
        return path
