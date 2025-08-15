import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from playwright.sync_api import sync_playwright

START_URL = "https://www.nme.com/artists/taylor-swift"
DOMAIN = "https://www.nme.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

visited = set()
to_visit = [START_URL]
articles = []

# Cutoff date: April 18, 2024 UTC
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)

def is_valid_article_url(url):
    if not url.startswith(DOMAIN):
        return False
    path = urlparse(url).path.lower()
    # Keep URLs that mention 'taylor-swift' but exclude the artist index page itself
    return "taylor-swift" in path and "/artists/taylor-swift" not in path

def extract_article_text(soup):
    article_tag = soup.find("article")
    if not article_tag:
        article_tag = soup.find("div", class_=lambda c: c and re.search(r"(article|entry)[-_ ]?(body|content)", c, re.I))
    if not article_tag:
        return ""
    paras = [
        p.get_text(" ", strip=True)
        for p in article_tag.find_all("p")
        if p.get_text(strip=True)
    ]
    return "\n\n".join(paras)

def extract_and_parse_date(soup):
    """
    Try multiple selectors to get date string, then parse into datetime with timezone awareness.
    Returns a datetime object or None if not found/parsable.
    """
    date_strings = []

    # Common meta tags for published date
    meta_time = soup.find("meta", property="article:published_time")
    if meta_time and meta_time.get("content"):
        date_strings.append(meta_time["content"])

    meta_time_alt = soup.find("meta", attrs={"name": "pubdate"})
    if meta_time_alt and meta_time_alt.get("content"):
        date_strings.append(meta_time_alt["content"])

    # <time datetime="...">
    time_tag = soup.find("time")
    if time_tag and time_tag.has_attr("datetime"):
        date_strings.append(time_tag["datetime"])

    # Try parsing each found date string
    for date_str in date_strings:
        try:
            dt = dateparser.parse(date_str)
            if dt is not None:
                # Make sure datetime is timezone-aware, assume UTC if naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception as e:
            print(f"Warning: Could not parse date '{date_str}': {e}")

    return None

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
            time.sleep(2)  # polite delay
        except Exception as e:
            print(f"Error loading {current_url}: {e}")
            continue

        soup = BeautifulSoup(page.content(), "html.parser")

        # Listing pages: enqueue article links
        if current_url == START_URL or "/page/" in current_url:
            for h3 in soup.find_all("h3", class_="text-2xl font-bold md:text-2xl"):
                parent = h3.parent
                link = None
                if parent.name == 'a' and parent.has_attr('href'):
                    link = urljoin(DOMAIN, parent['href'])
                else:
                    link_tag = h3.find_parent("a", href=True)
                    if link_tag:
                        link = urljoin(DOMAIN, link_tag['href'])

                if link and link not in visited and is_valid_article_url(link):
                    to_visit.append(link)
            continue

        # Article page: extract details
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

        dt = extract_and_parse_date(soup)
        if dt:
            print(f"  Found article date: {dt.isoformat()}")
        else:
            print("  Could not find or parse article date.")
            dt = None

        # Filter by cutoff date
        if dt and dt <= CUTOFF_DATE:
            print(f"  Skipping article older than cutoff date: {dt.date()}")
            continue  # skip old articles

        article_text = extract_article_text(soup)

        uid = hashlib.md5(current_url.encode()).hexdigest()

        articles.append({
            "title": title,
            "timestamp": dt.isoformat() if dt else "N/A",
            "uid": uid,
            "url": current_url,
            "text": article_text
        })

        # Enqueue more Taylor Swift article links from the article page
        for a in soup.find_all("a", href=True):
            href = urljoin(DOMAIN, a['href'])
            if href not in visited and is_valid_article_url(href):
                to_visit.append(href)

    browser.close()

# Save to JSON
output_file = "nme_taylor_swift_articles_filtered.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"✅ Crawl complete. {len(articles)} articles saved to {output_file}")

