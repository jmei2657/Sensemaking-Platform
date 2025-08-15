import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
from urllib.parse import urljoin, urlparse

start_url = "https://www.pbs.org/newshour/tag/taylor-swift/"
domain = "https://www.pbs.org"
visited = set()
to_visit = [start_url]
articles = []
headers = {"User-Agent": "Mozilla/5.0"}

def is_valid_article_url(url):
    if not url.startswith(domain):
        return False
    path = urlparse(url).path.lower()
    # Exclude tag/archive pages to avoid infinite loops
    if path.startswith("/tag/"):
        return False
    return "taylor-swift" in path

while to_visit:
    current_url = to_visit.pop(0)
    if current_url in visited:
        continue
    print(f"Visiting: {current_url}")
    visited.add(current_url)

    try:
        res = requests.get(current_url, headers=headers)
        if res.status_code != 200:
            print(f"Failed to fetch {current_url}, status: {res.status_code}")
            continue
    except Exception as e:
        print(f"Error fetching {current_url}: {e}")
        continue

    soup = BeautifulSoup(res.content, "html.parser")

    # If current URL is a tag/archive page, queue all Taylor Swift article links from it
    if current_url.startswith(start_url):
        for a in soup.find_all("a", href=True):
            href = urljoin(domain, a['href'])
            if href not in visited and is_valid_article_url(href):
                to_visit.append(href)
        # No article info to scrape here, continue to next URL
        continue

    # Otherwise, scrape article page info
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

    # Improved timestamp extraction:
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
            else:
                date_span = soup.find("span", class_="date")
                if date_span:
                    timestamp = date_span.get_text(strip=True)

    uid = hashlib.md5(current_url.encode()).hexdigest()

    articles.append({
        "title": title,
        "timestamp": timestamp,
        "uid": uid,
        "url": current_url
    })

    # Find all links on this article page to other Taylor Swift articles (avoid tag pages)
    for a in soup.find_all("a", href=True):
        href = urljoin(domain, a['href'])
        if href not in visited and is_valid_article_url(href):
            to_visit.append(href)

    time.sleep(1)  # polite delay

# Save all results
with open("pbs_taylor_articles_crawl.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"✅ Crawl complete. {len(articles)} articles saved to pbs_taylor_articles_crawl.json")
