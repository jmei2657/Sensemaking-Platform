import json
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

START_URL = "https://www.theguardian.com/music/taylor-swift"
BASE_URL = "https://www.theguardian.com"

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
            links.add(href.split("?")[0])  # Strip UTM params
    return list(links)

def parse_date_from_url(url):
    """Extract date from Guardian URL pattern and convert to timestamp"""
    # Guardian URLs can have multiple patterns:
    # /music/YYYY/MMM/DD/article-title
    # /music/YYYY/MMM/D/article-title (single digit day)
    # Also try more flexible patterns
    
    print(f"   🔍 Parsing date from URL: {url}")
    
    # Try different date patterns
    patterns = [
        r'/(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{1,2})/',
        r'(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{1,2})/',
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # Numeric format /2025/04/16/
        r'(\d{4})/(\d{1,2})/(\d{1,2})/',   # Without leading slash
    ]
    
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    for pattern in patterns:
        match = re.search(pattern, url.lower())
        if match:
            year = int(match.group(1))
            month_str = match.group(2)
            day = int(match.group(3))
            
            # Handle month - could be abbreviation or number
            if month_str.isdigit():
                month = int(month_str)
            else:
                month = month_map.get(month_str, 1)
            
            try:
                # Create datetime object and convert to timestamp
                dt = datetime(year, month, day)
                timestamp = int(dt.timestamp())
                formatted_date = dt.strftime('%Y-%m-%d')
                print(f"   ✅ Parsed date: {formatted_date} (timestamp: {timestamp})")
                return timestamp, formatted_date
            except ValueError as e:
                print(f"   ⚠️ Invalid date values: year={year}, month={month}, day={day} - {e}")
                continue
    
    print(f"   ❌ No date pattern found in URL: {url}")
    return None, None

def scrape_article(page, url):
    page.goto(url)
    page.wait_for_timeout(3000)
    soup = BeautifulSoup(page.content(), "html.parser")

    # Extract full article text paragraphs
    article_div = soup.find("div", {"data-gu-name": "body"})
    paragraphs = []
    if article_div:
        for p in article_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)

    # Extract publish date from time tag (fallback)
    time_tag = soup.find("time")
    meta_date = time_tag.get("datetime") if time_tag and time_tag.get("datetime") else "N/A"

    # Parse date from URL (primary method)
    url_timestamp, url_date = parse_date_from_url(url)

    # Extract title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

    # Generate UID based on URL
    uid = hashlib.md5(url.encode()).hexdigest()

    return {
        "url": url,
        "uid": uid,
        "date": url_date if url_date else "URL_DATE_NOT_FOUND",  # Always show if URL parsing failed
        "timestamp": url_timestamp,  # Unix timestamp
        "meta_date": meta_date,  # Keep original meta date as fallback
        "title": title,
        "context": " ".join(paragraphs) if paragraphs else ""
    }

def has_next_page(page_html):
    """Check if there's a next page available"""
    soup = BeautifulSoup(page_html, "html.parser")
    
    # Look for pagination links - Guardian uses various patterns
    # Check for "Next" button or numbered pagination
    next_links = soup.find_all("a", href=True)
    
    for link in next_links:
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        
        # Look for "next" text or page numbers in href
        if "next" in text or ("page=" in href and "taylor-swift" in href):
            return True
    
    return False

def scrape_page(page, page_num):
    """Scrape articles from a specific page number"""
    if page_num == 1:
        url = START_URL
    else:
        url = f"{START_URL}?page={page_num}"
    
    print(f"📄 Scraping page {page_num}: {url}")
    
    try:
        page.goto(url)
        page.wait_for_timeout(4000)
        
        # Check if page loaded successfully and has content
        page_html = page.content()
        soup = BeautifulSoup(page_html, "html.parser")
        
        # Check for 404 or empty page indicators
        if "404" in soup.get_text() or "not found" in soup.get_text().lower():
            print(f"   ⚠️ Page {page_num} appears to be 404 or not found")
            return [], False
        
        article_links = get_article_links(page_html)
        print(f"   Found {len(article_links)} article links on page {page_num}")
        
        # If no articles found, this might be the end
        if not article_links:
            print(f"   ⚠️ No article links found on page {page_num}")
            return [], False
        
        page_articles = []
        for article_url in article_links:
            print(f"   → Scraping: {article_url}")
            try:
                article = scrape_article(page, article_url)
                if article["date"] == "URL_DATE_NOT_FOUND":
                    print(f"   ⚠️ Could not parse date from URL: {article_url}")
                page_articles.append(article)
            except Exception as e:
                print(f"   ❌ Failed to scrape {article_url}: {e}")
        
        # Check if there's a next page
        has_more = has_next_page(page_html)
        
        return page_articles, has_more
        
    except Exception as e:
        print(f"❌ Failed to load page {page_num}: {e}")
        return [], False

def main():
    all_articles = []
    seen_urls = set()  # Track URLs to avoid duplicates across pages
    page_num = 1
    consecutive_empty_pages = 0
    max_consecutive_empty = 3  # Stop after 3 consecutive empty pages

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Keep scraping until we hit the end
        while True:
            page_articles, has_more_pages = scrape_page(page, page_num)
            
            # Filter out duplicates and add to main collection
            new_articles = []
            for article in page_articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    new_articles.append(article)
                    all_articles.append(article)
            
            print(f"   ✅ Added {len(new_articles)} new articles from page {page_num}")
            print(f"   📊 Total unique articles so far: {len(all_articles)}\n")
            
            # Check stopping conditions
            if len(page_articles) == 0:
                consecutive_empty_pages += 1
                print(f"⚠️ Empty page {page_num} (consecutive empty: {consecutive_empty_pages})")
                
                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"🛑 Stopping after {max_consecutive_empty} consecutive empty pages")
                    break
            else:
                consecutive_empty_pages = 0  # Reset counter if we found articles
            
            # Check if pagination indicates no more pages
            if not has_more_pages and len(page_articles) == 0:
                print(f"🛑 No more pages detected, stopping at page {page_num}")
                break
            
            # Safety valve - avoid infinite loops
            if page_num > 1000:  # Reasonable upper limit
                print(f"🛑 Safety stop at page {page_num} (unlikely to have more than 1000 pages)")
                break
            
            page_num += 1

        browser.close()

    # Save results
    output_file = "taylor_swift_guardian_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=4, ensure_ascii=False)

    print(f"🎉 Scraping complete!")
    print(f"📄 Pages scraped: {page_num}")
    print(f"📁 Total articles collected: {len(all_articles)}")
    print(f"💾 Data saved to '{output_file}'")

if __name__ == "__main__":
    main()