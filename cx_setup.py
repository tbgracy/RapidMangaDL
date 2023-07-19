import sys
from cx_Freeze import setup, Executable

package_name = "RapidMangaDL"
package_version = "0.1.3"
package_description = "Swiftly download manga from multiple sources."
package_author = "sifat"
package_author_email = "hossain0338@gmail.com"

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

base = None

executables = [Executable("manga_dl/main.py", base=base, target_name="manga-dl")]

classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Environment :: Web Environment",
    "Intended Audience :: End Users/Desktop",
    "Intended Audience :: Developers",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: MIT License",
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Software Development :: User Interfaces",
    "Topic :: Software Development :: Widget Sets",
    "Topic :: Utilities",
]

project_urls = {
    "Documentation": "https://github.com/shhossain/RapidMangaDL",
    "Issue Tracker": "https://github.com/shhossain/RapidMangaDL/issues",
    "Source Code": "https://github.com/shhossain/RapidMangaDL",
}

setup(
    name=package_name,
    version=package_version,
    description=package_description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=package_author,
    author_email=package_author_email,
    url="https://github.com/shhossain/RapidMangaDL",
    packages=["manga_dl"],
    package_data={"manga_dl": ["public/*", "templates/*"]},
    include_package_data=True,
    install_requires=requirements,
    classifiers=classifiers,
    python_requires=">=3.6",
    license="MIT",
    keywords="manga downloader",
    project_urls=project_urls,
    executables=executables,
)
