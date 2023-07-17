# RapidMangaDL

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

<!-- video cli.mp4 autoplay -->
https://github.com/shhossain/RapidMangaDL/assets/80335059/4c4cd91f-f0f9-4349-87ca-70af004be874



# Web-based GUI

The Web-based GUI offers a graphical interface to interact with the application. You can easily search for manga, select chapters, and initiate downloads.

To start the server, run:

```bash
manga-dl gui
```

Here's a sneak peek:

<!-- video gui.mp4 autoplay -->
https://github.com/shhossain/RapidMangaDL/assets/80335059/a4fc4d2e-0092-44dc-abea-77dd497ee47c



# Command Line Interface (CLI)

The CLI mode allows you to interact with the application using command-line arguments. Here's an example of how you can use it:

```bash
manga-dl cli -m https://manganato.com/manga-az963307 -c 1-10 -f epub -q 90
```

You can use the Command Line Interface (CLI) with arguments to initiate a download. Here's a breakdown of the available options:

```bash
usage: manga-dl [-h] [-s QUERY] [-m MANGA] [-c CHAPTERS] [-ex EXCLUDE] [-f {epub,pdf}] [-q QUALITY] [--host HOST] [-p PORT] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [mode]

positional arguments:
  mode                  Mode to run (choices: gui, prompt, cli)

optional arguments:
  -h, --help            show this help message and exit
  -s QUERY, --query QUERY
                        Search for a manga
  -m MANGA, --manga MANGA
                        Manga to download (Examples: -m https://manganato.com/manga-az963307 -m manga-id -m id -m manga-title (not reliable))
  -c CHAPTERS, --chapters CHAPTERS
                        Chapters to download (Examples: -c 1-10 -c 1,2,3 -c 1-10, 20-30 -c 1-10, 20-30, 40, 50, 60-70)
  -ex EXCLUDE, --exclude EXCLUDE
                        Chapters to exclude (Examples: -ex 1-10 -ex 1,2,3 -ex 1-10, 20-30 -ex 1-10, 20-30, 40, 50, 60-70)
  -f {epub,pdf}, --format {epub,pdf}
                        Format to download (choices: epub, pdf)
  -q QUALITY, --quality QUALITY
                        Quality of images (10-100)
  --host HOST           Host address of the server (default: 127.0.0.1)
  -p PORT, --port PORT  Port of the server (default: 80)
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the log level (choices: DEBUG, INFO, WARNING, ERROR, CRITICAL)
```
