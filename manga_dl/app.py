try:
    from manga import Manga, Chapter
    from tools import Downloader, logger, driver_manager as manager, get_app_path
except ImportError:
    from manga_dl.manga import Manga, Chapter
    from manga_dl.tools import (
        Downloader,
        logger,
        driver_manager as manager,
        get_app_path,
    )

import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
from multiprocessing import Value
from fake_headers import Headers
from urllib.parse import urlparse


headers = Headers().generate()

app = Flask(__name__, static_folder="public")
app.url_map.strict_slashes = False

temp_dir = os.environ.get("TEMP_DIR", os.path.join(get_app_path(), "tmp"))
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)


isDownloading = Value("i", 0)


@app.route("/", methods=["GET"])
@app.route("/index", methods=["GET"])
@app.route("/search", methods=["GET"])
def index():
    return render_template("search.html", results=[], query="")


@app.route("/search/<string:query>", methods=["GET"])
def search_query(query):
    query = query.replace("%%%", "/")
    mangas = Manga.search(query)
    return render_template("search.html", results=mangas, query=query)


@app.route("/manga/<string:manga_id>", methods=["GET"])
def manga(manga_id):
    manga = Manga.from_id(manga_id)
    manga.set_info()

    for chapter in manga.chapters:
        chapter[0] = f"/manga/{manga_id}/{chapter.id}"

    chapters = [chapter.to_json() for chapter in manga.chapters]
    chapters = json.dumps(chapters)

    return render_template("manga.html", manga=manga, chapters=chapters, downloading=isDownloading.value)  # type: ignore


def url_encode(s):
    return "-".join([str(ord(i)) for i in s])


def url_decode(s):
    return "".join([chr(int(i)) for i in s.split("-")])


@app.route("/manga/<string:manga_id>/<string:chapter_id>", methods=["GET"])
def manga_chapters(manga_id, chapter_id):
    manga = Manga.from_id(manga_id)
    manga.set_info()

    chapter_url = None
    chapter_idx = -1
    fchapter = None
    for idx, c in enumerate(manga.chapters):
        if c.eqal_id(chapter_id):
            chapter_url = c[0]
            fchapter = c
            chapter_idx = idx
            break

    if not chapter_url:
        return redirect(url_for("manga", manga_id=manga_id))

    for chapter in manga.chapters:
        chapter[0] = f"/manga/{manga_id}/{chapter.id}"

    chapter = Chapter.from_url(chapter_url)

    if chapter.source.use_selenium_in_get_chapter_img_urls:
        id, driver = manager.get_driver()
        imgs = chapter.get_chapter_imgs(driver=driver)
        manager.release_driver(id)
    else:
        imgs = chapter.get_chapter_imgs()

    return render_template(
        "chapter.html",
        imgs_urls=imgs,
        manga=manga,
        chapter=fchapter,
        chapter_idx=chapter_idx,
    )


################### API ####################


@app.route("/api/search", methods=["POST"])
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
        logger.error(f"Error getting search results: {e}")

    data = {
        "success": suc,
        "results": results,
    }

    if error:
        data["error"] = error

    return jsonify(data)


@app.route("/api/manga/download", methods=["POST"])
def manga_download():
    if isDownloading.value == 1:  # type: ignore
        return jsonify({"success": False, "message": "Only one download at a time"})

    isDownloading.value = 1  # type: ignore
    data = request.get_json()
    start_id = data["start_id"]
    end_id = data["end_id"]
    quality = data["quality"]
    dtypes = data["dtypes"]
    manga_id = data["manga_id"]

    quality = int(quality)

    manga = Manga.from_id(manga_id)
    manga.set_info()

    start = f"ID_{start_id}"
    end = f"ID_{end_id}"

    manga.select_chapters(f"{start}-{end}")

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
        logger.error(f"Error downloading manga: {e}")
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
    chapter_id = data["chapter_id"]

    sdata = {
        "success": True,
        "imgs": [],
    }

    manga = Manga.from_id(manga_id)
    chapter = None
    for c in manga.chapters:
        if c.eqal_id(chapter_id):
            chapter = c
            break
    if not chapter:
        sdata["success"] = False
        sdata["message"] = "Chapter not found"
        return jsonify(sdata)

    else:
        if chapter.source.use_selenium_in_get_chapter_img_urls:
            id, driver = manager.get_driver()
            imgs = chapter.get_chapter_imgs(driver=driver)
            manager.release_driver(id)
        else:
            imgs = chapter.get_chapter_imgs()

        sdata["imgs"] = imgs
        return jsonify(sdata)


@app.route("/api/img_url/<url>", methods=["GET"])
def img_url(url):
    url = url_decode(url)
    parse = urlparse(url)
    headers["referer"] = f"{parse.scheme}://{parse.netloc}"

    urlpath = Downloader.download_one(url, headers=headers, download_dir=temp_dir)

    with open(urlpath.filepath, "rb") as f:
        return f.read(), 200, {"Content-Type": "image/jpeg"}


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=80)
    app.run()
