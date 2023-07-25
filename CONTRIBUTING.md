# How to Contribute by Adding a New Source to the Manga Downloader (manga_dl) Repository

In this tutorial, we will guide you through the process of contributing to the Manga Downloader repository by adding a new manga source. A manga source is responsible for providing information about manga, searching for manga, retrieving chapters' URLs, and downloading images. We will follow the conventions and structure already present in the repository.

## Step 1: Fork the Repository

To begin contributing, first, fork the Manga Downloader repository on GitHub by clicking the "Fork" button in the top right corner of the repository page.

## Step 2: Clone the Forked Repository

Clone your forked repository to your local machine using the following command:

```bash
git clone https://github.com/Auto-Life/RapidMangaDL
```

## Step 3: Create a New File for Your Source

Navigate to the manga_sources folder inside the manga_dl directory. Create a new file with the name of your source. For example, if you are adding a source named "My Manga Source", the file name should be my_manga_source.py. The file name should be in snake_case.

## Step 4: Implement Your Source Class

Create a new Python file inside the folder you just created. In this file, you will define your source class by inheriting from the BaseSource class and implementing three main functions: search, get_info, and get_chapter_img_urls. Additionally, you need to define the domain, alternate_domains, and manga_format class attributes for your source. For example:

```python
# manga_dl/manga_sources/your_source_folder/your_source.py

from .base_source import BaseSource
from .utils import MangaInfo, Chapter, scraper, static_exists, exists


class YourSource(BaseSource):
    domain = "your_source_domain.com"
    alternate_domains = ["alternate_domain1.com", "alternate_domain2.com"]
    manga_format = "https://{domain}/manga/{ID}"

    @staticmethod
    @static_exists("https://your_source_domain.com/search")
    def search(query: str) -> list[MangaInfo]:
        # Implement your search functionality here
        # Use web scraping or API requests to search for manga based on the query
        # Parse the search results and create a list of MangaInfo objects
        # Each MangaInfo object should contain at least title and URL of the manga
        # Example:
        results = []
        manga1 = MangaInfo(title="Manga 1", url="https://your_source_domain.com/manga/manga1")
        manga2 = MangaInfo(title="Manga 2", url="https://your_source_domain.com/manga/manga2")
        results.append(manga1)
        results.append(manga2)
        return results

    @exists
    def get_info(self) -> MangaInfo:
        # Implement fetching detailed manga information here
        # Use web scraping or API requests to get the information based on self.url
        # Create a MangaInfo object containing details about the manga
        # Example:
        manga_info = MangaInfo(title="Manga Title", url=self.url)
        manga_info.cover_url = "https://your_source_domain.com/covers/manga_cover.jpg"
        manga_info.authors = ["Author 1", "Author 2"]
        manga_info.genres = ["Action", "Adventure", "Fantasy"]
        manga_info.description = "This is a description of the manga."
        # Add more information as needed
        return manga_info

    @exists
    def get_chapter_img_urls(self, chapter_url: str, **kw) -> list[str]:
        # Implement fetching image URLs for a specific chapter here
        # Use web scraping or API requests to get the image URLs based on chapter_url
        # Return a list of image URLs as strings
        # Example:
        img_urls = [
            "https://your_source_domain.com/chapters/chapter1/img1.jpg",
            "https://your_source_domain.com/chapters/chapter1/img2.jpg",
            "https://your_source_domain.com/chapters/chapter1/img3.jpg",
        ]
        return img_urls

```

## Step 5: Implement the Search Function

The search function is responsible for searching for manga based on a given query. It should return a list of MangaInfo objects, each containing information about a manga. Use web scraping or API requests to retrieve the search results and parse them into MangaInfo objects.

## Step 6: Implement the Get Info Function

The get_info function should fetch detailed information about a manga based on its URL. It should return a MangaInfo object containing all relevant details about the manga, such as title, cover URL, authors, genres, description, and chapter information.

## Step 7: Implement the Get Chapter Image URLs Function

The get_chapter_img_urls function should retrieve the URLs of the manga images for a specific chapter. You may need to use web scraping or API requests to obtain the image URLs. Return the list of image URLs as strings.

## Step 8: Add Your Source to the **init**.py File

In the manga_dl/manga_sources/**init**.py file, import your source class and add it to the sources list. For example:

```python
# manga_dl/manga_sources/__init__.py

from .source1 import MangaNato, Bato, ONEkissmanga, BaseSource, Chapter, MangaInfo
from .source2 import YourSource

sources = [MangaNato, Bato, ONEkissmanga, YourSource]  # Add your source class here
```

## Step 9: Test Your Source

As testing is not yet implemented, you can test your source by running the main.py file and using the command line interface.

## Step 10: Commit and Push Your Changes

Once you are satisfied with your source, commit and push your changes to your forked repository. Then, create a pull request to merge your changes into the main repository.

## Step 11: Review and Address Feedback

Be prepared to receive feedback and suggestions for improvement from the repository maintainers. Address any issues or suggestions raised during the code review process.

## Step 12: Celebrate!

Congratulations! You have successfully contributed to the Manga Downloader repository. Your source will be added to the main repository and will be available for use by all users.

## Step 13: Keep Contributing!

You can continue contributing to the repository by adding more sources or by improving the existing code. You can also contribute by reporting bugs and issues or by suggesting new features.

# Examples of Manga Sources

You can find examples of manga sources in the manga_dl/manga_sources folder. You can use these examples as a reference when implementing your own source.

- [MangaNato](https://github.com/Auto-Life/RapidMangaDL/blob/main/manga_dl/manga_sources/source1.py#L23)
- [Bato](https://github.com/Auto-Life/RapidMangaDL/blob/main/manga_dl/manga_sources/source1.py#L322)
- [ONEkissmanga](https://github.com/Auto-Life/RapidMangaDL/blob/main/manga_dl/manga_sources/source1.py#L201)


