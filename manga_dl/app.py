import nest_asyncio
nest_asyncio.apply()


import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
from manga import Manga, Chapter
import os
from fake_headers import Headers
from multiprocessing import Value
from tools import Downloader


headers = Headers().generate()
headers["referer"] = "https://chapmanganato.com/"

app = Flask(__name__, static_folder="public")
temp_dir = "tmp"
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


logger = app.logger

isDownloading = Value("i", 0)


@app.route("/", methods=["GET"])
@app.route("/index", methods=["GET"])
@app.route("/search", methods=["GET"])
def index():
    return render_template("search.html", results=[], query="")


@app.route("/search/<string:query>", methods=["GET"])
def search_query(query):
    mangas = Manga.search(query)
    return render_template("search.html", results=mangas, query=query)


@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data["query"]

    suc = True
    results = []
    error = ""
    try:
        if query:
            mangas = Manga.search(query)
            results = [i.to_json() for i in mangas]
        else:
            suc = False
            error = "No query provided"
    except Exception as e:
        suc = False
        error = "Unknown error"
        logger.error(e, exc_info=True)

    data = {
        "success": suc,
        "results": results,
    }

    if error:
        data["error"] = error

    return jsonify(data)


@app.route("/manga/<string:manga_id>", methods=["GET"])
def manga(manga_id):
    manga = Manga.from_id(manga_id)
    try:
        manga.set_info()
    except Exception as e:
        logger.error(e, exc_info=True)

    for chapter in manga.chapters:
        if chapter[0].endswith("/"):
            chapter[0] = chapter[0][:-1]
        chapter[0] = f"/manga/{manga_id}/{chapter[0].split('/')[-1]}"

    chapters = [chapter.to_json() for chapter in manga.chapters]
    chapters = json.dumps(chapters)

    return render_template("manga.html", manga=manga, chapters=chapters, downloading=isDownloading.value)  # type: ignore


def url_encode(s):
    # convert to to ascii with - as the separator
    return "-".join([str(ord(i)) for i in s])


def url_decode(s):
    # convert back to string
    return "".join([chr(int(i)) for i in s.split("-")])


@app.route("/manga/<string:manga_id>/<string:chapter>", methods=["GET"])
def manga_chapters(manga_id, chapter):
    manga = Manga.from_id(manga_id)
    try:
        manga.set_info()
    except Exception as e:
        logger.error(e, exc_info=True)

    chapter_url = None
    chapter_idx = -1
    fchapter = None
    for idx, c in enumerate(manga.chapters):
        if c[0].endswith("/"):
            c[0] = c[0][:-1]

        if c[0].endswith(chapter):
            chapter_url = c[0]
            fchapter = c
            chapter_idx = idx
            break

    if not chapter_url:
        return redirect(url_for("manga", manga_id=manga_id))

    for chapter in manga.chapters:
        if chapter[0].endswith("/"):
            chapter[0] = chapter[0][:-1]
        chapter[0] = f"/manga/{manga_id}/{chapter[0].split('/')[-1]}"
    

    chapter = Chapter.from_url(chapter_url)
    imgs = chapter.img_urls
    # img_urls = [f"/api/img_url/{url_encode(i)}" for i in imgs]

    return render_template(
        "chapter.html",
        imgs_urls=imgs,
        manga=manga,
        chapter=fchapter,
        chapter_idx=chapter_idx,
    )


@app.route("/api/manga/download", methods=["POST"])
def manga_download():
    if isDownloading.value == 1:  # type: ignore
        return jsonify({"success": False, "message": "Only one download at a time"})

    isDownloading.value = 1  # type: ignore
    data = request.get_json()
    start_url = data["start_url"]
    end_url = data["end_url"]
    quality = data["quality"]
    dtypes = data["dtypes"]

    if start_url.endswith("/"):
        start_url = start_url[:-1]
    if end_url.endswith("/"):
        end_url = end_url[:-1]

    manga_id = start_url.split("/")[2]

    # replace manga/ with manga-
    start_url = start_url.replace("manga/", "manga-")
    end_url = end_url.replace("manga/", "manga-")
    start_url = f"https://chapmanganato.com{start_url}"
    end_url = f"https://chapmanganato.com{end_url}"
    quality = int(quality)

    print("Download:", start_url, end_url, quality, dtypes)

    manga = Manga.from_id(manga_id)
    manga.select_chapters(f"{start_url}-{end_url}")

    data = {"success": True, "paths": []}
    try:
        paths = []
        for dtype in dtypes:
            if dtype == "pdf":
                path = manga.create_pdf(quality=quality)
            else:
                path = manga.create_epub(quality=quality)
            paths.append(os.path.abspath(path))
        data["paths"] = paths
    except Exception as e:
        logger.error(e, exc_info=True)
        data["success"] = False
        data["message"] = "Unknown error"

    isDownloading.value = 0  # type: ignore

    return jsonify(data)


@app.route("/api/manga/download/progress", methods=["GET"])
def manga_download_progress():
    data = {
        "success": True,
        "progress": json.loads(
            os.environ.get(
                "PROGRESS_BAR",
                json.dumps({"total": 0, "current": 0, "desc": "Downloading"}),
            )
        ),
        "isDownloading": True if isDownloading.value == 1 else False,  # type: ignore
    }
    return jsonify(data)


@app.route("/api/manga/imgs", methods=["POST"])
def manga_chapter_img():
    data = request.get_json()
    manga_id = data["manga_id"]
    chapter_url = data["chapter_url"]

    sdata = {
        "success": True,
        "imgs": [],
    }

    manga = Manga.from_id(manga_id)
    try:
        manga.set_info()
    except Exception as e:
        logger.error(e, exc_info=True)
        sdata["success"] = False
        sdata["error"] = "Unknown error"

    # manga/dg980989/chapter-70
    chapter_url = chapter_url.replace("manga/", "manga-")
    url = f"https://chapmanganato.com/{chapter_url}"
    chapter = Chapter.from_url(url)
    imgs = chapter.img_urls
    sdata["imgs"] = imgs
    return jsonify(sdata)


@app.route("/api/img_url/<url>", methods=["GET"])
def img_url(url):
    url = url_decode(url)
    urlpath = Downloader.download_one(url, headers=headers, download_dir=temp_dir)

    with open(urlpath.filepath, "rb") as f:
        return f.read(), 200, {"Content-Type": "image/jpeg"}




if __name__ == "__main__":
    app.run(host="0.0.0.0",port=80)
