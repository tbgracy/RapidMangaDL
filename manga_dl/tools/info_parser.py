from bs4 import BeautifulSoup
from cloudscraper import create_scraper
from .exceptions import MangaNotFound

scraper = create_scraper(
    browser={"browser": "firefox", "platform": "windows", "mobile": False}
)

def get_manganato_info(url):
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
            chapter_title = atag.text.strip()  # type: ignore
            chapter_views = chapter.select_one(".chapter-view").text.strip()  # type: ignore
            chapter_upload_date = chapter.select_one(".chapter-time").text.strip()  # type: ignore
            chapters.append(Chapter(chapter_url, chapter_title, chapter_views, chapter_upload_date))  # type: ignore

        if ";" in alt:
            alt = alt.split(";")[0].strip()
    
    except Exception as e:
        logger.error(e, exc_info=True)
        raise MangaNotFound("Manga not found")