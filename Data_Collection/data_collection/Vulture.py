from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib
import json
import time
from urllib.parse import urljoin

ARTIST_NAME = "Taylor Swift"
POPCRUSH_START_URL = "https://popcrush.com/tags/taylor-swift/"
POPCRUSH_DOMAIN = "https://popcrush.com"
POPCRUSH_CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)
POPCRUSH_OUTPUT_FILE = f"popcrush_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"

VULTURE_START_URL = "https://www.vulture.com/taylor-swift/"
VULTURE_DOMAIN = "https://www.vulture.com"
VULTURE_OUTPUT_FILE = f"vulture_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"


def extract_article_text_popcrush(soup):
    content = soup.find("div", class_="content") or soup.find("article")
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))


def extract_and_parse_date_popcrush(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        try:
            return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
        except Exception as e:
            print(f"Date parse error: {e}")
            return None
    return None


def should_keep_article(title, text):
    full = f"{title} {text}".lower()
    return ARTIST_NAME.lower() in full


def get_article_links_popcrush(soup):
    return [urljoin(POPCRUSH_DOMAIN, a["href"]) for a in soup.select("a.title[href]") if "/ixp/" in a["href"]]


def scrape_popcrush():
    articles = []
    visited_links = set()
    uids_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page_num = 1
        while True:
            url = POPCRUSH_START_URL if page_num == 1 else f"{POPCRUSH_START_URL}page/{page_num}/"
            print(f"\nVisiting PopCrush page: {url}")
            try:
                page.goto(url, timeout=60000)
                page.wait_for_selector("a.title", timeout=15000)
            except PlaywrightTimeoutError:
                print("❌ Page timeout.")
                break

            soup = BeautifulSoup(page.content(), "html.parser")
            links = list(set(get_article_links_popcrush(soup)))
            print(f"📰 Found {len(links)} article links on page {page_num}.")

            found_new_valid = False

            for link in links:
                if link in visited_links:
                    continue
                visited_links.add(link)

                uid = hashlib.md5(link.encode()).hexdigest()
                if uid in uids_seen:
                    continue

                try:
                    print(f"  Visiting article: {link}")
                    page.goto(link, timeout=30000)
                    page.wait_for_selector("h1", timeout=10000)
                    article_soup = BeautifulSoup(page.content(), "html.parser")

                    title_tag = article_soup.find("h1")
                    title = title_tag.get_text(strip=True) if title_tag else "No Title"

                    date = extract_and_parse_date_popcrush(article_soup)
                    if not date or date <= POPCRUSH_CUTOFF_DATE:
                        print("    ⏩ Skipped (too old or no date)")
                        continue

                    text = extract_article_text_popcrush(article_soup)
                    if not should_keep_article(title, text):
                        print("    ❌ Skipped (no artist match)")
                        continue

                    articles.append({
                        "uid": uid,
                        "title": title,
                        "timestamp": date.isoformat(),
                        "url": link,
                        "text": text
                    })
                    uids_seen.add(uid)
                    found_new_valid = True
                    print(f"    ✅ Saved: {title}")

                except PlaywrightTimeoutError:
                    print(f"    ⛔ Timeout on article {link}")

            if not found_new_valid:
                print("🚫 No valid new articles on this page. Stopping.")
                break

            page_num += 1

        browser.close()

    with open(POPCRUSH_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ PopCrush crawl complete. {len(articles)} articles saved to {POPCRUSH_OUTPUT_FILE}")


def scrape_vulture():
    articles = []
    visited_links = set()
    uids_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\nVisiting Vulture page: {VULTURE_START_URL}")
        try:
            page.goto(VULTURE_START_URL, timeout=60000)
            page.wait_for_selector("a.feed-link", timeout=15000)
        except PlaywrightTimeoutError:
            print("❌ Page timeout.")
            browser.close()
            return

        soup = BeautifulSoup(page.content(), "html.parser")
        links = []
        for a in soup.select("a.feed-link[href]"):
            href = urljoin(VULTURE_DOMAIN, a["href"])
            if href not in visited_links:
                links.append(href)
                visited_links.add(href)

        print(f"📰 Found {len(links)} article links on Vulture main page.")

        for link in links:
            uid = hashlib.md5(link.encode()).hexdigest()
            if uid in uids_seen:
                continue

            try:
                print(f"  Visiting article: {link}")
                page.goto(link, timeout=30000)
                page.wait_for_selector("h1", timeout=10000)
                article_soup = BeautifulSoup(page.content(), "html.parser")

                title_tag = article_soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else "No Title"

                # Date extraction for Vulture (example: from <time datetime="...">)
                time_tag = article_soup.find("time", {"datetime": True})
                if time_tag:
                    date_str = time_tag["datetime"]
                    try:
                        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except Exception:
                        date = None
                else:
                    date = None

                if not date or date <= POPCRUSH_CUTOFF_DATE:
                    print("    ⏩ Skipped (too old or no date)")
                    continue

                text = extract_article_text_popcrush(article_soup)  # reuse function; might need tweaking
                if not should_keep_article(title, text):
                    print("    ❌ Skipped (no artist match)")
                    continue

                articles.append({
                    "uid": uid,
                    "title": title,
                    "timestamp": date.isoformat() if date else "N/A",
                    "url": link,
                    "text": text
                })
                uids_seen.add(uid)
                print(f"    ✅ Saved: {title}")

            except PlaywrightTimeoutError:
                print(f"    ⛔ Timeout on article {link}")

        browser.close()

    with open(VULTURE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Vulture crawl complete. {len(articles)} articles saved to {VULTURE_OUTPUT_FILE}")


if __name__ == "__main__":
    scrape_popcrush()
    scrape_vulture()
