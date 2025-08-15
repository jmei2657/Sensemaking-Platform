from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib
import json
import time
from urllib.parse import urljoin

ARTIST_NAME = "Taylor Swift"
BUSTLE_START_URL = "https://www.bustle.com/search?q=taylor+swift"
BUSTLE_DOMAIN = "https://www.bustle.com"
BUSTLE_OUTPUT_FILE = f"bustle_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)


def extract_article_text_bustle(soup):
    content = soup.find("article") or soup.find("div", class_="article-body")
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))


def extract_and_parse_date_bustle(soup):
    time_tag = soup.find("time", datetime=True)
    if time_tag and time_tag.has_attr("datetime"):
        try:
            return datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
        except Exception as e:
            print(f"Date parse error: {e}")
    return None


def should_keep_article(title, text):
    full = f"{title} {text}".lower()
    return ARTIST_NAME.lower() in full


def get_article_links_bustle(soup):
    return [urljoin(BUSTLE_DOMAIN, a["href"]) for a in soup.select("a.ofI[href]") if "/entertainment/" in a["href"]]


def scrape_bustle():
    articles = []
    visited_links = set()
    uids_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\nVisiting Bustle search page: {BUSTLE_START_URL}")
        try:
            page.goto(BUSTLE_START_URL, timeout=60000)
            page.wait_for_selector("a.ofI", timeout=15000)
        except PlaywrightTimeoutError:
            print("❌ Page timeout.")
            browser.close()
            return

        soup = BeautifulSoup(page.content(), "html.parser")
        links = get_article_links_bustle(soup)
        print(f"📰 Found {len(links)} article links on Bustle search page.")

        for link in links:
            uid = hashlib.md5(link.encode()).hexdigest()
            if link in visited_links or uid in uids_seen:
                continue

            visited_links.add(link)
            try:
                print(f"  Visiting article: {link}")
                page.goto(link, timeout=30000)
                page.wait_for_selector("h1", timeout=10000)
                article_soup = BeautifulSoup(page.content(), "html.parser")

                title_tag = article_soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else "No Title"

                date = extract_and_parse_date_bustle(article_soup)
                if not date or date <= CUTOFF_DATE:
                    print("    ⏩ Skipped (too old or no date)")
                    continue

                text = extract_article_text_bustle(article_soup)
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
                print(f"    ✅ Saved: {title}")

            except PlaywrightTimeoutError:
                print(f"    ⛔ Timeout on article {link}")

        browser.close()

    with open(BUSTLE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Bustle crawl complete. {len(articles)} articles saved to {BUSTLE_OUTPUT_FILE}")


if __name__ == "__main__":
    scrape_bustle()
