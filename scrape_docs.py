"""
scrape_docs.py

Downloads Ubuntu Desktop documentation pages from the web
and saves them as plain text files into the ./docs/ folder.
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

START_URL = "https://help.ubuntu.com/stable/ubuntu-help/index.html"
BASE_DOMAIN = "help.ubuntu.com"

DOCS_FOLDER = "docs"

DELAY_SECONDS = 0.5
MAX_PAGES = 150

def make_safe_filename(url: str) -> str:
    """Turn a URL into a safe filename we can save to disk."""
    path = urlparse(url).path
    name = path.strip("/").replace("/", "_")
    if not name.endswith(".txt"):
        name = name.replace(".html", "") + ".txt"
    if not name:
        name = "index.txt"
    return name


def get_page_text(url: str) -> tuple[str, list[str]]:
    """
    Fetch a page, extract the readable text and all links.
    Returns (clean_text, list_of_links).
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠  Could not fetch {url}: {e}")
        return "", []

    soup = BeautifulSoup(resp.text, "html.parser")

    main = (
        soup.find("div", {"id": "content"})
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )

    text = main.get_text(separator="\n", strip=True) if main else ""

    links = []
    for tag in soup.find_all("a", href=True):
        full = urljoin(url, tag["href"])
        if urlparse(full).netloc == BASE_DOMAIN and full.endswith(".html"):
            links.append(full)

    return text, links


def scrape():
    """Crawl Ubuntu help pages and save them as .txt files."""
    os.makedirs(DOCS_FOLDER, exist_ok=True)

    visited = set()
    queue = [START_URL]
    saved = 0

    print(f"Starting scrape from: {START_URL}")
    print(f"Saving docs to:       ./{DOCS_FOLDER}/")
    print(f"Max pages:            {MAX_PAGES}\n")

    while queue and saved < MAX_PAGES:
        url = queue.pop(0)

        if url in visited:
            continue
        visited.add(url)

        print(f"[{saved+1:>3}/{MAX_PAGES}] Fetching: {url}")
        text, links = get_page_text(url)

        if text.strip():
            filename = make_safe_filename(url)
            filepath = os.path.join(DOCS_FOLDER, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Source: {url}\n\n")
                f.write(text)

            saved += 1

        for link in links:
            if link not in visited:
                queue.append(link)

        time.sleep(DELAY_SECONDS)

    print(f"\nDone! Saved {saved} pages to ./{DOCS_FOLDER}/")
    print("Next step: run  python build_index.py  to build the search index.")


if __name__ == "__main__":
    scrape()
