from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib
import json
import time
from urllib.parse import urljoin

ARTIST_NAME = "Taylor Swift"
UPROXX_START_URL = "https://uproxx.com/topic/taylor-swift/"
UPROXX_DOMAIN = "https://uproxx.com"
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)
OUTPUT_FILE = f"uproxx_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"

def extract_article_text(soup):
    # Usually articles content is inside div with class containing "article" or "content"
    content = soup.find("div", class_=lambda x: x and ("article" in x or "content" in x))
    if not content:
        content = soup.find("article")
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

def extract_and_parse_date(soup):
    # Try meta tag first
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        try:
            return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
        except Exception as e:
            print(f"Date parse error (meta): {e}")

    # Try <time datetime="...">
    time_tag = soup.find("time", {"datetime": True})
    if time_tag:
        try:
            return datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
        except Exception as e:
            print(f"Date parse error (time tag): {e}")

    return None

def should_keep_article(title, text):
    full = f"{title} {text}".lower()
    return ARTIST_NAME.lower() in full

def scrape_uproxx():
    articles = []
    visited_links = set()
    uids_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Loading {UPROXX_START_URL}")
        try:
            page.goto(UPROXX_START_URL, timeout=60000)
            time.sleep(5)  # wait for JS content to load
            # Scroll to bottom to trigger lazy loading
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(3)
            page.wait_for_selector('a[href*="taylor-swift"]', timeout=10000)
        except PlaywrightTimeoutError:
            print("❌ Timeout waiting for articles or slow load - trying to parse what is available")

        soup = BeautifulSoup(page.content(), "html.parser")
        links = [urljoin(UPROXX_DOMAIN, a['href']) for a in soup.select('a[href*="taylor-swift"]')]
        print(f"Found {len(links)} article links on Uproxx page")

        for link in links:
            if link in visited_links:
                continue
            visited_links.add(link)

            uid = hashlib.md5(link.encode()).hexdigest()
            if uid in uids_seen:
                continue

            try:
                print(f"Visiting article: {link}")
                page.goto(link, timeout=30000)
                page.wait_for_selector("h1", timeout=10000)
                article_soup = BeautifulSoup(page.content(), "html.parser")

                title_tag = article_soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else "No Title"

                date = extract_and_parse_date(article_soup)
                if not date or date <= CUTOFF_DATE:
                    print(f"  ⏩ Skipped (too old or no date): {date}")
                    continue

                text = extract_article_text(article_soup)
                if not should_keep_article(title, text):
                    print("  ❌ Skipped (no artist match)")
                    continue

                articles.append({
                    "uid": uid,
                    "title": title,
                    "timestamp": date.isoformat(),
                    "url": link,
                    "text": text
                })
                uids_seen.add(uid)
                print(f"  ✅ Saved: {title}")

            except PlaywrightTimeoutError:
                print(f"  ⛔ Timeout on article {link}")

        browser.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Uproxx crawl complete. {len(articles)} articles saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_uproxx()
