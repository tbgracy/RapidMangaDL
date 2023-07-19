import logging
import math
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


from PIL import Image
from fuzzywuzzy import fuzz


try:
    from tools import (
        Downloader,
        PDFChapter,
        PDF,
        create_failure_image,
        get_file_name,
        URLFile,
        replace_unimportant,
        logger,
        http_split,
        tqdm,
        driver_manager as manager,
        get_app_path,
    )

    from tools.exceptions import MangaNotFound

    from manga_sources import Chapter, MangaInfo, BaseSource, get_source, sources  # type: ignore

except ImportError:
    from manga_dl.tools import (
        Downloader,
        PDFChapter,
        PDF,
        create_failure_image,
        get_file_name,
        URLFile,
        replace_unimportant,
        logger,
        http_split,
        tqdm,
        driver_manager as manager,
        get_app_path,
    )

    from manga_dl.tools.exceptions import MangaNotFound
    from manga_dl.manga_sources import (
        Chapter,
        MangaInfo,
        BaseSource,
        get_source,
        sources,
    )

app_path = get_app_path()
temp_dir = os.path.join(app_path, "temp")
os.environ["TEMP_DIR"] = os.environ.get("TEMP_DIR", temp_dir)
temp_dir = os.environ["TEMP_DIR"]
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


class Manga:
    def __init__(self, url: str):  # type: ignore
        """
        Manga object

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
                return cls(inp)
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

    def chapters_exists(
        self, inputs, chapters: list[Chapter]
    ) -> dict[Union[str, int], list[Chapter]]:
        """
        Checks if the given inputs are valid chapters

        Parameters
        ----------
        inputs : Union[str, int, list[str], list[int]]
            The inputs to check
        chapters : list[Chapter]
            The chapters to check against

        Returns
        -------
        dict[Union[str, int], list[Chapter]]
            A dict with the inputs as keys and the chapters as values

        Examples
            >>> chapters_exists("1", manga.chapters)
            >>> chapters_exists(["1", "2"], manga.chapters)
        """

        if inputs is None:
            return {}

        if isinstance(inputs, str):
            inputs = [inputs]

        chapter_url_dict = {i.url: i for i in chapters}
        chapters_title_dict = {i.title: i for i in chapters}
        selected_chapters = {}
        for i in inputs:
            if not i:
                selected_chapters[i] = []

            if isinstance(i, str):
                if i.startswith("latest") or i.startswith("last"):
                    ii = i.replace("latest", "").replace("last", "")
                    ii = replace_unimportant(ii)
                    if ii.isdigit():
                        int_ii = int(ii)
                        selected_chapters[i] = chapters[-int_ii:]
                    else:
                        selected_chapters[i] = chapters[-5:]

                elif i.count("http") == 1:
                    if i in chapter_url_dict:
                        selected_chapters[i] = [chapter_url_dict[i]]

                elif i.isdigit():
                    int_i = int(i)
                    if int_i < len(chapters):
                        selected_chapters[str(i)] = [chapters[int_i]]

                elif "," in i:
                    if "http" in i:
                        vals = http_split(i, ",")
                    else:
                        ii = replace_unimportant(i, but=["-", ","])
                        vals = [a.strip() for a in ii.split(",")]
                    schapters = self.chapters_exists(vals, chapters)
                    selected_chapters[i] = [i for a in schapters.values() for i in a]

                elif "-" in i:
                    if "http" not in i:
                        ii = replace_unimportant(i, but=["-", ","])
                        vals = [i.strip() for i in ii.split("-")]
                    else:
                        vals = http_split(i, "-")

                    schapters = self.chapters_exists(vals, chapters)
                    ct1 = chapters.count(schapters[vals[0]][0])
                    start_index = -1
                    if ct1 > 0:
                        start_index = chapters.index(schapters[vals[0]][0])
                    ct2 = chapters.count(schapters[vals[1]][0])
                    end_index = -1
                    if ct2 > 0:
                        end_index = chapters.index(schapters[vals[1]][0])
                    if start_index > -1 and end_index > -1:
                        selected_chapters[i] = chapters[start_index:end_index]

                elif i.startswith("ID"):
                    chapter = None
                    for ch in chapters:
                        if ch.eqal_id(i.replace("ID", "").replace("_", "")):
                            chapter = ch
                            break
                    selected_chapters[i] = [chapter]

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

    def _get_save_chapters_str(self, selected_chapters: list[Chapter]):
        # if len is less than 4 then just indexs else range and total chapters
        if len(selected_chapters) < 4:
            return ",".join([i.short_name for i in selected_chapters])
        else:
            return f"{selected_chapters[0].short_name}-{selected_chapters[-1].short_name}_total_{len(selected_chapters)}"

    def select_chapters(
        self,
        selected: Union[str, int, Chapter, None],
        exclude: Union[str, int, Chapter, None] = None,
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

        chapters_url_dict = {i.url: [0, i] for i in chapters}
        for i in chapters:
            chapters_url_dict[i.url][0] += 1

        self.chapters = []
        for i in chapters_url_dict.values():
            if i[0] > 0:
                self.chapters.append(i[1])

        self._save_chapters_str = f"{self._get_save_chapters_str(self.chapters)}"

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

        else:
            logger.info(
                "Using Selenium to get chapter img urls (this may take a while)"
            )

            driver = manager.get_driver()
            for chapter in tqdm(self.chapters, desc="Getting Chapter Imgs"):
                chapter.get_chapter_imgs(driver=driver[1])
            manager.release_driver(driver[0])

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
                with tqdm(
                    total=len(futures), desc=f"Lowering quality to {quality}"
                ) as bar:
                    for future in cf.as_completed(futures):
                        filename, qfilename = future.result()
                        chapter = img_filenames_chapter[filename]
                        chapter.add_qfile((filename, qfilename))
                        bar.update(1)

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
            with tqdm(total=len(items), desc="Creating PDF chapters") as bar:
                with cf.ThreadPoolExecutor() as executor:
                    for item in executor.map(create_chapter, nitems):
                        items.append(item)
                        bar.update(1)

        return items

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
        if not path:
            path = filename
        else:
            if not os.path.isdir(path):
                os.makedirs(path)
            path = os.path.join(path, filename)

        logger.info(f"Manga(create_epub): Saving to {path}")
        epub.write_epub(path, book)
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

        if not path:
            path = filename
        else:
            if not os.path.isdir(path):
                os.makedirs(path)

            path = os.path.join(path, filename)

        pdf.write(path)
        logger.info(f"Manga(create_pdf): Saving to {path}")

        return path
