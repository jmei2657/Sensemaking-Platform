import json
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

START_URL = "https://www.theguardian.com/music/taylor-swift"
BASE_URL = "https://www.theguardian.com"
CUTOFF_TIMESTAMP = 1713398400  # April 18, 2024 UTC

def get_article_links(page_html):
    soup = BeautifulSoup(page_html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/music/" in href and "taylor-swift" in href:
            if href.startswith("/"):
                href = BASE_URL + href
            elif not href.startswith("http"):
                href = BASE_URL + "/" + href
            links.add(href.split("?")[0])
    return list(links)

def parse_date_from_url(url):
    # Fixed regex patterns - was missing \d in first pattern
    patterns = [
        r'/(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{1,2})/',
        r'(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{1,2})/',
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',
        r'(\d{4})/(\d{1,2})/(\d{1,2})/'
    ]
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    print(f"Parsing date from: {url}")
    
    for pattern in patterns:
        match = re.search(pattern, url.lower())
        if match:
            year = int(match.group(1))
            month_str = match.group(2)
            day = int(match.group(3))
            month = int(month_str) if month_str.isdigit() else month_map.get(month_str, 1)
            try:
                dt = datetime(year, month, day)
                parsed_date = dt.strftime('%Y-%m-%d')
                print(f"✅ Parsed: {parsed_date}")
                return int(dt.timestamp()), parsed_date
            except ValueError:
                continue
    
    print(f"❌ Could not parse date from: {url}")
    return None, None

def scrape_article(page, url):
    print(f"Scraping article: {url}")
    page.goto(url)
    page.wait_for_timeout(3000)
    soup = BeautifulSoup(page.content(), "html.parser")
    
    article_div = soup.find("div", {"data-gu-name": "body"})
    paragraphs = [p.get_text(strip=True) for p in article_div.find_all("p")] if article_div else []
    
    time_tag = soup.find("time")
    meta_date = time_tag.get("datetime") if time_tag and time_tag.get("datetime") else "N/A"
    
    url_timestamp, url_date = parse_date_from_url(url)
    
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"
    
    uid = hashlib.md5(url.encode()).hexdigest()
    
    return {
        "url": url,
        "uid": uid,
        "date": url_date or "URL_DATE_NOT_FOUND",
        "timestamp": url_timestamp,
        "meta_date": meta_date,
        "title": title,
        "context": " ".join(paragraphs)
    }

def scrape_all_articles():
    all_articles = []
    seen_urls = set()
    page_num = 1
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while True:
            url = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f"\n📄 Scraping page {page_num}: {url}")
            
            try:
                page.goto(url)
                page.wait_for_timeout(4000)
                page_html = page.content()
                article_links = get_article_links(page_html)
                print(f"Found {len(article_links)} article links on page {page_num}")

                new_articles = 0
                for article_url in article_links:
                    if article_url in seen_urls:
                        continue
                    
                    try:
                        article = scrape_article(page, article_url)
                        
                        # Skip articles older than cutoff date
                        if article["timestamp"] and article["timestamp"] <= CUTOFF_TIMESTAMP:
                            print(f"⏭️ Skipping old article: {article['date']}")
                            continue
                        
                        seen_urls.add(article_url)
                        all_articles.append(article)
                        new_articles += 1
                        print(f"✅ Added article: {article['title'][:50]}...")
                        
                    except Exception as e:
                        print(f"❌ Failed to scrape article {article_url}: {e}")

                print(f"📊 Added {new_articles} new articles from page {page_num}")
                print(f"📈 Total articles collected: {len(all_articles)}")
                
                if new_articles == 0:
                    print("🛑 No new articles found on this page, stopping.")
                    break

                page_num += 1

            except Exception as e:
                print(f"❌ Error on page {page_num}: {e}")
                break

        browser.close()

    # Save to JSON file
    output_file = "taylor_swift_guardian_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Scraping complete!")
    print(f"📁 Total articles saved: {len(all_articles)}")
    print(f"💾 Data saved to: {output_file}")

if __name__ == "__main__":
    scrape_all_articles()