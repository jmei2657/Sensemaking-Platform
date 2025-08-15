from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib, json, time, re
from urllib.parse import urljoin

START_URL = "https://variety.com/t/billie-eilish/"
DOMAIN = "https://variety.com"
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)
output_file = "variety_billie_eilish_articles.json"

articles = []
visited = set()

def is_valid_article_url(url):
    return (
        url.startswith(DOMAIN)
        and "/news/" in url or "/music/" in url or re.search(r"/\d{4}/\d{2}/\d{2}/", url)
        and not any(x in url for x in ["#comment", "#respond", "?replytocom="])
    )

def extract_article_text(soup):
    content = soup.find("article") or soup.find("div", class_="article__content")
    if not content:
        return ""
    paragraphs = content.find_all("p")
    return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

def extract_and_parse_date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        dt = datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
        return dt
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print(f"Visiting: {START_URL}")
    try:
        page.goto(START_URL, timeout=60000)
        page.wait_for_selector('h3.c-title a', timeout=15000)

        # Scroll to load more articles
        for _ in range(10):  # Adjust for how many pages to scroll
            page.mouse.wheel(0, 4000)
            time.sleep(2)

        soup = BeautifulSoup(page.content(), "html.parser")
        links = [urljoin(DOMAIN, a["href"]) for a in soup.select("h3.c-title a[href]")]
        links = list(set(filter(is_valid_article_url, links)))

        print(f"📰 Found {len(links)} potential article links.")

        for link in links:
            if link in visited:
                continue
            visited.add(link)

            try:
                print(f"Visiting article: {link}")
                page.goto(link, timeout=30000)
                page.wait_for_selector("h1", timeout=10000)
                article_soup = BeautifulSoup(page.content(), "html.parser")

                title_tag = article_soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else "No Title"

                date = extract_and_parse_date(article_soup)
                if not date or date <= CUTOFF_DATE:
                    print("  ⏩ Skipped due to date filter.")
                    continue

                text = extract_article_text(article_soup)
                uid = hashlib.md5(link.encode()).hexdigest()

                articles.append({
                    "uid": uid,
                    "title": title,
                    "timestamp": date.isoformat(),
                    "url": link,
                    "text": text
                })

            except PlaywrightTimeoutError:
                print(f"⛔ Timeout loading {link}")
                continue

    except PlaywrightTimeoutError:
        print(f"❌ Failed to load listing page {START_URL}")

    browser.close()

# Save output
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"✅ Crawl complete. {len(articles)} articles saved to {output_file}")
