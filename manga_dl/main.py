import os
import questionary as qs
import argparse
import webbrowser
import sys
import logging

try:
    from app import app
    from tools import logger, run_with_cloudflared
    from manga import Manga
except ImportError:
    from manga_dl.app import app
    from manga_dl.tools import logger, run_with_cloudflared
    from manga_dl.manga import Manga




helps = {
    "manga": "Manga to download\nExamples: \n\t -m https://manganato.com/manga-az963307\n\t -m manga-id\n\t -m id\n\t -m manga-title (not relaible)",
    "chapters": "Chapters to download\nExamples: \n\t -c 1-10\n\t -c 1,2,3\n\t -c 1-10, 20-30\n\t -c 1-10, 20-30, 40, 50, 60-70",
    "exclude": "Chapters to exclude\nExamples: \n\t -ex 1-10\n\t -ex 1,2,3\n\t -ex 1-10, 20-30\n\t -ex 1-10, 20-30, 40, 50, 60-70",
}


def prompt(query=None):
    if query is None:
        query = qs.text(
            "Search for a manga:",
            validate=lambda x: True if len(x) > 0 else "Must be at least 1 character",
        ).ask()
    while True:
        mangas = Manga.search(query=query)
        if len(mangas) == 0:
            print("No results found.")
            query = qs.text(
                "Search for a manga:",
                validate=lambda x: True
                if len(x) > 0
                else "Must be at least 1 character",
            ).ask()
        else:
            break

    mangas_dict = {f"{i+1}. {manga.title} ({manga.source.current_domain})": manga for i, manga in enumerate(mangas)}
    manga = qs.select("Select a manga:", choices=list(mangas_dict.keys())).ask()
    manga = mangas_dict[manga]
    manga.set_info()
    # show total chapters
    print(f"Total chapters: {manga.total_chapters}")
    # ask if user wants to download all chapters or a range
    choice = qs.select(
        "Download all chapters or a range?", choices=["All", "Select", "Custom"]
    ).ask()
    if choice == "Select":
        # show all chapters
        chapters = qs.checkbox(
            "Select chapters:", choices=[chapter.title for chapter in manga.chapters]
        ).ask()
        manga.select_chapters(chapters)
    elif choice == "Custom":
        # show example of custom input
        print(helps["chapters"].replace("-c ", ""))
        print(helps["exclude"])
        print("Full Example:\n\t 1-10, 20-30, 40, 50, 60-70 -ex 2,3,4")
        # ask for custom input
        custom = qs.text("Enter custom input:").ask()
        # parse custom input
        vals = custom.split("-ex ")
        exclude = None
        chapters = vals[0]
        if len(vals) == 2:
            exclude = vals[1]
        
        manga.select_chapters(chapters, exclude=exclude)
        
    # select epub or pdf
    choices = qs.checkbox(
        "Select formats:", choices=["epub", "pdf"], default="epub"
    ).ask()
    # quality 1-100
    quality = qs.text(
        "Select quality:",
        default="100",
        validate=lambda x: True
        if x.isdigit() and int(x) in range(1, 101)
        else "Must be a number between 1-100",
    ).ask()
    quality = int(quality)
    # download
    for choice in choices:
        if choice == "epub":
            manga.create_epub(quality=quality)
        elif choice == "pdf":
            manga.create_pdf(quality=quality)
    # ask if user wants to download another manga
    choice = qs.select("Download another manga?", choices=["Yes", "No"]).ask()
    if choice == "Yes":
        prompt()
    else:
        print("Goodbye!")
        


def cli(args):
    if args.query:
        prompt(args.query)
    
    if args.manga:
        manga = Manga.autodetect(args.manga)
        logger.info(f"Detected manga: {manga.title} ({manga.source.current_domain})")
        manga.select_chapters(args.chapters, exclude=args.exclude)

        quality = max(10, min(100, args.quality))
        logger.info(f"Quality: {quality}")
        
        if not args.format:
            args.format = "epub"
            logger.info(f"Format not specified, defaulting to {args.format}")    

        logger.info(f"Format: {args.format}")
        logger.info(f"Dowloading {manga.title}...")
        if args.format == "epub":
            manga.create_epub(quality=quality)
        elif args.format == "pdf":
            manga.create_pdf(quality=quality)

        logger.info("Done!")
        sys.exit(0)
        
    


def parser():
    parser = argparse.ArgumentParser(
        description="Manga Downloader",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("mode",nargs="?" , choices=["gui", "prompt", "cli"], help="Mode to run", default="prompt")
    parser.add_argument("-s", "--query", help="Search for a manga")
    parser.add_argument("-m", "--manga", help=helps["manga"])
    parser.add_argument("-c", "--chapters", help=helps["chapters"])
    parser.add_argument("-ex", "--exclude", help=helps["exclude"])
    parser.add_argument(
        "-f",
        "--format",
        choices=["epub", "pdf"],
        help="Format to download epub or pdf",
    )
    parser.add_argument(
        "-q", "--quality", type=int, default=100, help="Quality of images 10-100"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host address of server")
    parser.add_argument("-p", "--port", default=80, type=int, help="Port of server")
    parser.add_argument("--share", action="store_true", help="Share the server in public")
    parser.add_argument(
        "-l",
        "--log",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )

    args = parser.parse_args()

    if args.log:
        logger.setLevel(args.log)
    

    if args.mode == "gui":
        try:
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            fcli = sys.modules['flask.cli']
            fcli.show_server_banner = lambda *x: None # type: ignore
        except Exception as e:
            logger.error(f"Erorr occured while disabling flask logs {e}")
            logger.info("Continuing without disabling flask logs")
            
        if args.share:
           try:
                run_with_cloudflared(app)
           except Exception as e:
                logger.error(f"Error occured while running with cloudflared {e}")
                logger.info("Running without cloudflared")
        
        host = args.host
        if host == "0.0.0.0":
            host = "127.0.0.1"
        
        print("   Ctrl+C to exit")
        print(f" * Running on http://{host}:{args.port} (Private)")
        webbrowser.open(f"http://{host}:{args.port}")
        app.run(host=args.host, port=args.port)
        

    elif args.mode == "prompt":
        prompt()

    elif args.mode == "cli":
        cli(args)
        

def main():
    try:
        parser()
    except KeyboardInterrupt:
        print("Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error occured {e}")
        logger.info("Rest assured, all downloaded files are automatically cached. Run the program again to continue downloading.")
        sys.exit(1)
        

if __name__ == "__main__":
    main()

    
