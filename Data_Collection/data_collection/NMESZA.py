import re
import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime
from dateutil import parser as dateparser
from playwright.sync_api import sync_playwright

start_url = "https://nme-next.netlify.app/artists/sza"
domain = "https://www.nme.com"

visited = set()
to_visit = [start_url]
articles = []
headers = {"User-Agent": "Mozilla/5.0"}

# Cutoff date - don't scrape articles before this
CUTOFF_DATE = datetime(2024, 4, 18)

def is_valid_article_url(url: str) -> bool:
    """Limit crawl to SZA-related NME pages that are not the artist index itself."""
    if not url.startswith(domain):
        return False
    path = urlparse(url).path.lower()
    return "sza" in path and "/artists/sza" not in path

def extract_article_text(soup: BeautifulSoup) -> str:
    """
    Return visible paragraph text from an NME article page.
    Falls back to common 'article-body' / 'entry-content' containers.
    """
    article_tag = soup.find("article")
    if not article_tag:
        article_tag = soup.find(
            "div",
            class_=lambda c: c and re.search(r"(article|entry)[-_ ]?(body|content)", c, re.I),
        )
    if not article_tag:
        return ""

    paras = [
        p.get_text(" ", strip=True)
        for p in article_tag.find_all("p")
        if p.get_text(strip=True)
    ]
    return "\n\n".join(paras)

def parse_iso_date(date_str: str) -> datetime | None:
    try:
        return dateparser.parse(date_str)
    except Exception:
        return None

def scrape_article(page, url: str) -> dict | None:
    print(f"Visiting article: {url}")
    try:
        page.goto(url, timeout=30000)
        page.wait_for_timeout(3000)
        soup = BeautifulSoup(page.content(), "html.parser")

        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

        timestamp = "N/A"
        meta_time = (soup.find("meta", property="article:published_time") or
                     soup.find("meta", attrs={"name": "pubdate"}))
        if meta_time and meta_time.get("content"):
            timestamp = meta_time["content"]
        else:
            time_tag = soup.find("time")
            if time_tag and time_tag.has_attr("datetime"):
                timestamp = time_tag["datetime"]

        article_date = parse_iso_date(timestamp)
        if not article_date:
            print(f"⚠️ Could not parse date for article {url}, skipping.")
            return None

        # Fix timezone-aware vs naive datetime issue:
        if article_date.tzinfo is not None:
            article_date = article_date.replace(tzinfo=None)

        # Skip article if date before cutoff
        if article_date < CUTOFF_DATE:
            print(f"🛑 Article dated {article_date.date()} before cutoff, skipping: {url}")
            return None

        text = extract_article_text(soup)

        uid = hashlib.md5(url.encode()).hexdigest()
        return {
            "title": title,
            "timestamp": timestamp,
            "uid": uid,
            "url": url,
            "text": text,
            "date": article_date.strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while to_visit:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            print(f"Visiting: {current_url}")
            visited.add(current_url)

            try:
                page.goto(current_url, timeout=30000)
                page.wait_for_timeout(2000)
                html = page.content()
            except Exception as e:
                print(f"Error loading {current_url}: {e}")
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Listing pages
            if current_url == start_url or "/page/" in current_url:
                for h3 in soup.find_all("h3", class_="text-2xl font-bold md:text-2xl"):
                    parent_link = (
                        h3.parent if h3.parent.name == "a" and h3.parent.has_attr("href") else
                        h3.find_parent("a", href=True)
                    )
                    if parent_link:
                        link = urljoin(domain, parent_link["href"])
                        if link not in visited and is_valid_article_url(link):
                            to_visit.append(link)
                continue

            # Article pages
            article = scrape_article(page, current_url)
            if article:
                articles.append(article)
                # Queue more SZA article links inside this article
                for a in soup.find_all("a", href=True):
                    href = urljoin(domain, a["href"])
                    if href not in visited and is_valid_article_url(href):
                        to_visit.append(href)

            time.sleep(1)  # polite delay

        browser.close()

    # Save results
    with open("nme_sza_articles_playwright.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=4)

    print(f"✅ Crawl complete. {len(articles)} articles with text saved to nme_sza_articles_playwright.json")

if __name__ == "__main__":
    main()
