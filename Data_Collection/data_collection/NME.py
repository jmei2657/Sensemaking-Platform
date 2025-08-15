import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
from urllib.parse import urljoin, urlparse

start_url = "https://www.nme.com/artists/taylor-swift"
domain = "https://www.nme.com"

visited = set()
to_visit = [start_url]
articles = []
headers = {"User-Agent": "Mozilla/5.0"}

def is_valid_article_url(url):
    if not url.startswith(domain):
        return False
    path = urlparse(url).path.lower()
    # Only keep URLs that mention 'taylor-swift' to keep focus
    return "taylor-swift" in path and "/artists/taylor-swift" not in path

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
        # Find all h3 with the specific class for article titles
        for h3 in soup.find_all("h3", class_="text-2xl font-bold md:text-2xl"):
            title = h3.get_text(strip=True)
            # Try to find link inside or near h3
            parent = h3.parent
            link = None
            if parent.name == 'a' and parent.has_attr('href'):
                link = urljoin(domain, parent['href'])
            else:
                # maybe the parent or grandparent contains a link
                link_tag = h3.find_parent("a", href=True)
                if link_tag:
                    link = urljoin(domain, link_tag['href'])

            if link and link not in visited and is_valid_article_url(link):
                to_visit.append(link)
        continue  # go next URL after queuing article pages

    # On article page: extract title, timestamp, uid, url

    # Extract title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

    # Extract timestamp from meta tags or time elements
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

    uid = hashlib.md5(current_url.encode()).hexdigest()

    articles.append({
        "title": title,
        "timestamp": timestamp,
        "uid": uid,
        "url": current_url
    })

    # Find new links in the article to other Taylor Swift articles
    for a in soup.find_all("a", href=True):
        href = urljoin(domain, a['href'])
        if href not in visited and is_valid_article_url(href):
            to_visit.append(href)

    time.sleep(1)  # polite delay

# Save results
with open("nme_taylor_swift_articles.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"✅ Crawl complete. {len(articles)} articles saved to nme_taylor_swift_articles.json")
