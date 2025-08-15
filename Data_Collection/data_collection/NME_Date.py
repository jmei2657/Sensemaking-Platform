import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
import os
from urllib.parse import urljoin, urlparse
from datetime import datetime

start_url = "https://www.nme.com/artists/taylor-swift"
domain = "https://www.nme.com"
output_file = "nme_taylor_swift_articles.json"
cutoff_date = datetime(2025, 5, 19)  # May 19, 2025

visited = set()
to_visit = [start_url]
headers = {"User-Agent": "Mozilla/5.0"}

def is_valid_article_url(url):
    if not url.startswith(domain):
        return False
    path = urlparse(url).path.lower()
    # Only keep URLs that mention 'taylor-swift' to keep focus
    return "taylor-swift" in path and "/artists/taylor-swift" not in path

def parse_date(timestamp_str):
    """Parse various date formats and return datetime object"""
    if not timestamp_str or timestamp_str == "N/A":
        return None
    
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
        "%Y-%m-%dT%H:%M:%S",    # ISO format without timezone
        "%Y-%m-%d %H:%M:%S",    # Standard format
        "%Y-%m-%d",             # Date only
        "%d/%m/%Y",             # UK format
        "%m/%d/%Y",             # US format
    ]
    
    for fmt in formats:
        try:
            # Attempt parsing directly first
            return datetime.strptime(timestamp_str[:19], fmt[:19])
        except ValueError:
            continue
    
    print(f"Warning: Could not parse date: {timestamp_str}")
    return None

def is_date_after_cutoff(timestamp_str):
    parsed_date = parse_date(timestamp_str)
    if parsed_date is None:
        return False  # Skip articles with unparseable dates
    return parsed_date > cutoff_date

def load_existing_articles():
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_articles_to_json(articles_list):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(articles_list, f, ensure_ascii=False, indent=4)
    print(f"Saved {len(articles_list)} articles to {output_file}")

# Load existing articles
all_articles = load_existing_articles()
existing_urls = {article.get('url') for article in all_articles}
print(f"Loaded {len(all_articles)} existing articles")

articles_scraped_this_session = 0

while to_visit:
    current_url = to_visit.pop(0)
    if current_url in visited:
        continue
    print(f"Visiting: {current_url}")
    visited.add(current_url)

    try:
        res = requests.get(current_url, headers=headers)
        if res.status_code != 200:
            print(f"Failed to fetch {current_url}: Status {res.status_code}")
            continue
    except Exception as e:
        print(f"Error fetching {current_url}: {e}")
        continue

    soup = BeautifulSoup(res.content, "html.parser")

    # On the start page or listing pages: find article URLs near h3 titles
    if current_url == start_url or "/page/" in current_url:
        for h3 in soup.find_all("h3", class_="text-2xl font-bold md:text-2xl"):
            # Try to find link inside or near h3
            parent = h3.parent
            link = None
            if parent.name == 'a' and parent.has_attr('href'):
                link = urljoin(domain, parent['href'])
            else:
                link_tag = h3.find_parent("a", href=True)
                if link_tag:
                    link = urljoin(domain, link_tag['href'])

            if link and link not in visited and is_valid_article_url(link):
                to_visit.append(link)
        continue

    if current_url in existing_urls:
        print(f"Skipping already scraped article: {current_url}")
        continue

    # Extract title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

    # Extract timestamp
    timestamp = "N/A"
    meta_time = soup.find("meta", property="article:published_time")
    if meta_time and meta_time.get("content"):
        timestamp = meta_time["content"]
    else:
        meta_time = soup.find("meta", attrs={"name": "pubdate"})
        if meta_time and meta_time.get("content"):
            timestamp = meta_time["content"]
        else:
            time_tag = soup.find("time")
            if time_tag and time_tag.has_attr("datetime"):
                timestamp = time_tag["datetime"]

    if not is_date_after_cutoff(timestamp):
        print(f"Skipping article before cutoff date: {title} ({timestamp})")
        continue

    # Extract article full text from the div.article-content
    content_div = soup.find("div", class_="article-content")
    if content_div:
        paragraphs = content_div.find_all("p")
        article_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
    else:
        article_text = "N/A"

    uid = hashlib.md5(current_url.encode()).hexdigest()

    article_data = {
        "title": title,
        "timestamp": timestamp,
        "uid": uid,
        "url": current_url,
        "text": article_text
    }

    all_articles.append(article_data)
    existing_urls.add(current_url)
    articles_scraped_this_session += 1

    print(f"Added article: {title} ({timestamp})")

    if articles_scraped_this_session % 10 == 0:
        save_articles_to_json(all_articles)
        print(f"Batch save completed. Total articles: {len(all_articles)}")

    # Find new links in the article to other Taylor Swift articles
    for a in soup.find_all("a", href=True):
        href = urljoin(domain, a['href'])
        if href not in visited and is_valid_article_url(href):
            to_visit.append(href)

    time.sleep(1)  # polite delay

# Final save for any remaining articles
if articles_scraped_this_session % 10 != 0:
    save_articles_to_json(all_articles)

print(f"Crawl complete!")
print(f"Articles scraped this session: {articles_scraped_this_session}")
print(f"Total articles in database: {len(all_articles)}")
print(f"Results saved to {output_file}")
