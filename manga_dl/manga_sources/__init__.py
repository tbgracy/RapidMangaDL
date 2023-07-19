from .source1 import MangaNato, Bato, ONEkissmanga, BaseSource, Chapter, MangaInfo

sources = [MangaNato, Bato, ONEkissmanga]

class SourceNotFound(Exception):
    pass

def all_domains() -> list[str]:
    return [domain for source in sources for domain in source.all_domains()]


def get_source(url: str) -> BaseSource:
    for source in sources:
        if source.is_valid(url):
            return source(url)
    raise SourceNotFound(
        f"Source not found for {url}\nAvailable sources: {', '.join(all_domains())}"
    )
