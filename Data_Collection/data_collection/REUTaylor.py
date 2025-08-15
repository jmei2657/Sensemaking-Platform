from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib, json, time
from urllib.parse import urljoin

ARTIST_NAME = "Taylor Swift"
BASE_SEARCH_URL = "https://www.reuters.com/site-search/?query=taylor+swift&offset={offset}"
REUTERS_DOMAIN = "https://www.reuters.com"
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)
OUTPUT_FILE = f"reuters_{ARTIST_NAME.lower().replace(' ', '_')}_articles.json"

def extract_article_text(soup):
    # Reuters article body usually inside div with data-testid='Body'
    content = soup.find("div", {"data-testid": "Body"})
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

def extract_and_parse_date(soup):
    # Try meta tag first
    meta = soup.find("meta", {"name": "article:published_time"})
    if meta and meta.get("content"):
        try:
            return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
        except Exception as e:
            print(f"Date parse error (meta): {e}")

    # Try time tag with datetime attribute
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

def scrape_reuters():
    articles = []
    visited_links = set()
    offset = 0
    max_no_new_pages = 3  # Stop if no new articles found in this many pages

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        no_new_pages = 0

        while True:
            search_url = BASE_SEARCH_URL.format(offset=offset)
            print(f"\nLoading search results page with offset={offset}: {search_url}")

            try:
                page.goto(search_url, timeout=60000)
                page.wait_for_selector('a[data-testid="TitleLink"]', timeout=15000)
            except PlaywrightTimeoutError:
                print("❌ Timeout waiting for search results or slow load - trying to parse what is available")

            soup = BeautifulSoup(page.content(), "html.parser")
            links = [urljoin(REUTERS_DOMAIN, a["href"]) for a in soup.select('a[data-testid="TitleLink"]')]
            print(f"Found {len(links)} article links on this search page")

            new_articles_found = False

            for link in links:
                if link in visited_links:
                    continue
                visited_links.add(link)

                try:
                    print(f"Visiting article: {link}")
                    page.goto(link, timeout=30000)
                    page.wait_for_selector("h1", timeout=10000)
                    article_soup = BeautifulSoup(page.content(), "html.parser")

                    title_tag = article_soup.find("h1")
                    title = title_tag.get_text(strip=True) if title_tag else "No Title"

                    date = extract_and_parse_date(article_soup)
                    if not date or date <= CUTOFF_DATE:
                        print(f"  ⏩ Skipped due to date filter: {date}")
                        continue

                    text = extract_article_text(article_soup)
                    if not should_keep_article(title, text):
                        print("  ❌ Skipped (no artist match)")
                        continue

                    uid = hashlib.md5(link.encode()).hexdigest()
                    articles.append({
                        "uid": uid,
                        "title": title,
                        "timestamp": date.isoformat(),
                        "url": link,
                        "text": text
                    })
                    new_articles_found = True
                    print(f"  ✅ Saved: {title}")

                except PlaywrightTimeoutError:
                    print(f"  ⛔ Timeout loading article {link}")
                    continue

            if not new_articles_found:
                no_new_pages += 1
                print(f"No new articles found on page offset={offset} (count {no_new_pages}/{max_no_new_pages})")
                if no_new_pages >= max_no_new_pages:
                    print("Stopping search, no new articles found in last pages.")
                    break
            else:
                no_new_pages = 0

            offset += 20  # Reuters increments offset by 20 per search page

        browser.close()

    # Save output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Reuters crawl complete. {len(articles)} articles saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_reuters()
