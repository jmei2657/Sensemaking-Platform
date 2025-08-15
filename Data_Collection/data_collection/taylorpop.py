from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib, json, time
from urllib.parse import urljoin

ARTIST_NAME = "Taylor Swift"
START_URL = "https://popcrush.com/tags/taylor-swift/"
DOMAIN = "https://popcrush.com"
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)
OUTPUT_FILE = f"popcrush_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"

articles = []
visited_links = set()
uids_seen = set()

def extract_article_text(soup):
    content = soup.find("div", class_="content") or soup.find("article")
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

def extract_and_parse_date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        try:
            return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
        except:
            return None
    return None

def should_keep_article(title, text):
    full = f"{title} {text}".lower()
    return ARTIST_NAME.lower() in full

def get_article_links(soup):
    return [urljoin(DOMAIN, a["href"]) for a in soup.select("a.title[href]") if "/ixp/" in a["href"]]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page_num = 1
    while True:
        url = START_URL if page_num == 1 else f"{START_URL}page/{page_num}/"
        print(f"\nVisiting page: {url}")
        try:
            page.goto(url, timeout=60000)
            page.wait_for_selector("a.title", timeout=15000)
        except PlaywrightTimeoutError:
            print("❌ Page timeout.")
            break

        soup = BeautifulSoup(page.content(), "html.parser")
        links = list(set(get_article_links(soup)))
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

                title = article_soup.find("h1")
                title = title.get_text(strip=True) if title else "No Title"

                date = extract_and_parse_date(article_soup)
                if not date or date <= CUTOFF_DATE:
                    print("    ⏩ Skipped (too old or no date)")
                    continue

                text = extract_article_text(article_soup)
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

# Save output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n✅ Crawl complete. {len(articles)} articles saved to {OUTPUT_FILE}")
