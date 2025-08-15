import re
import requests
from bs4 import BeautifulSoup

URL = (
    "https://www.nme.com/news/music/"
    "taylor-swifts-new-album-midnights-breaks-record-for-most-streamed-album-in-a-day-on-spotify-3333916"
)

HEADERS = {
    # Pretend to be a normal browser – helps avoid 403s and paywall stubs
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def get_article_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()                       # 4xx/5xx → explode early

    soup = BeautifulSoup(resp.text, "lxml")

    # 1️⃣  Find the main article element (preferred).
    article_tag = soup.find("article")

    # 2️⃣  Fallback: common divs if <article> isn’t present.
    if article_tag is None:
        article_tag = soup.find(
            "div",
            class_=lambda c: c
            and bool(re.search(r"(article|entry)[-_ ]?(body|content)", c, re.I)),
        )

    if article_tag is None:                       # Still nothing? Bail.
        raise RuntimeError("Could not locate article container.")

    paragraphs = [
        p.get_text(" ", strip=True)
        for p in article_tag.find_all("p")
        if p.get_text(strip=True)
    ]

    return "\n\n".join(paragraphs)


if __name__ == "__main__":
    text = get_article_text(URL)
    # 👉 Do what you like here:
    print(text)                       # show in console
    # Path("nme_midnights.txt").write_text(text, encoding="utf-8")  # or save to file
