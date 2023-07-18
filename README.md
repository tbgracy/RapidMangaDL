# RapidMangaDL (Manga Downloader)

RapidMangaDL is a Python package that allows you to swiftly download manga from various sources. It offers multiple ways to interact with the application, including a Command Line Interface (CLI) and an Interactive CLI with a text-based prompt. Additionally, it comes with a web-based GUI to provide a user-friendly experience.
[Suppoted Sources](/sources.md)

## Installation

To install Manga Downloader, you can use `pip`:

```bash
pip install RapidMangaDL
```

# Features

Download manga from multiple sources with great speed.
Three different ways to interact with the application: CLI, Interactive CLI, and Web-based GUI.
Select specific chapters or a custom range for downloading.
Choose between downloading the manga in EPUB or PDF format.
Customize the quality of the images (10 to 100).

# Interactive CLI 

The Interactive CLI mode provides a user-friendly prompt to search for a manga, select chapters, specify the format, and set image quality.

To start the Interactive CLI mode, simply run:

```bash
manga-dl
```

Here's a quick demo:

![CLI](https://github.com/shhossain/RapidMangaDL/raw/main/cli.gif)

# Web-based GUI (Graphical User Interface)

The Web-based GUI offers a graphical interface to interact with the application. You can easily search for manga, select chapters, and initiate downloads.

To start the server, run:

```bash
manga-dl gui
```

Here's a sneak peek:

![WEB DEMO](https://github.com/shhossain/RapidMangaDL/raw/main/web_gui.gif)

To create a shareable link, you can use the `--share` flag:

```bash
manga-dl gui --share
```

# Command Line Interface (CLI)

The CLI mode allows you to interact with the application using command-line arguments. Here's an example of how you can use it:

```bash
manga-dl cli -m https://manganato.com/manga-az963307 -c 1-10 -f epub -q 90
```

You can use the Command Line Interface (CLI) with arguments to initiate a download. Here's a breakdown of the available options:

```bash
usage: manga-dl [-h] [-s QUERY] [-m MANGA] [-ss SOURCE] [-c CHAPTERS] [-ex EXCLUDE] [-f {epub,pdf}] [-q QUALITY] [--host HOST] [-p PORT]  [mode]

positional arguments:
  mode                  Mode to run (choices: gui, prompt, cli) [Web ui, Interactive CLI, CLI]

optional arguments:
  -h, --help            show this help message and exit
  -s QUERY, --query QUERY
                        Search for a manga (This will move to interactive mode with the search results)
  -m MANGA, --manga MANGA
                        Manga to download 
                        Examples:
                        -m https://manganato.com/manga-az963307 (most reliable)
                        -m manga-id (from web gui something like this managato_uq971673)
                        -m manga-title (Match by similarity, not relaiable)
  -ss SOURCE, --source SOURCE
                        Source to download from (Examples: -ss manganato | -ss mangakakalot | -ss manganelo | -ss mangasee123) 
  -c CHAPTERS, --chapters CHAPTERS
                        Chapters to download
                          Examples: 
                          -c 1-10 | -c 1,2,3 | -c 1-10, 20-30 | -c 1-10, 20-30, 40, 50, 60-70 | -c latest 10 | -c Chapter 1, Chapter 2 |
                          -c https://manganato.com/manga-az963307/chapter-1-https://manganato.com/manga-az963307/chapter-2
                          -c last (last 5 chapters)
                          
  -ex EXCLUDE, --exclude EXCLUDE
                        Chapters to exclude (same rules apply as --chapters)
  -f {epub,pdf}, --format {epub,pdf}
                        Format to download (choices: epub, pdf)
  -q QUALITY, --quality QUALITY
                        Quality of images (10-100)
  --host HOST           Host address of the server (default: 127.0.0.1)
  -p PORT, --port PORT  Port of the server (default: 80)
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the log level (choices: DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

# Python API

You can also use the Python API to interact with the application.

Selecting a manga

```python
from manga_dl import Manga

manga = Manga("https://manganato.com/manga-az963307")
manga.set_info()

print(manga.title)
print(manga.author)
print(manga.description)

```

Selecting from search results

```python

mangas = Manga.search("one piece")
manga = mangas[0]
manga.set_info()

print(manga.title)
```


Selecting chapters

```python

manga.select_chapters("1-10")
# or
manga.select_chapters("1,2,3,4,5,6,7,8,9,10")
# or
manga.select_chapters("1-10, 20-30, 40, 50, 60-70")
# or
managa.select_chapters("Chapter 1, Chapter 2")
# or
managa.select_chapters("https://manganato.com/manga-az963307/chapter-1-https://manganato.com/manga-az963307/chapter-2")

# exclude chapters
manga.select_chapters("1-10", exclude="5") # same rules apply for exclude
```

Downloading

```python
manga.create_epub()
# or
manga.create_pdf()

# specify quality
manga.create_epub(quality=70) # Default is 85(unchangable)

# specify output directory
manga.create_epub(path="C:/Users/username/Desktop")
```

Luanching the server

```python
from manga_dl import app

app.run()
# or
app.run(host="localhost", port=80) # app is a Flask app
```
