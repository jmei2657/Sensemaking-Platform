import requests
from bs4 import BeautifulSoup
import time
import re
import json

BASE_URL = "https://timesofindia.indiatimes.com"
START_URL = "https://timesofindia.indiatimes.com/topic/Taylor-Swift/news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def clean_text(text):
    return text.strip().replace("\n", " ").replace("\r", " ")

def extract_uid_from_url(url):
    match = re.search(r'/(\d+)\.cms', url)
    if match:
        return match.group(1)
    return None

def scrape_article_page(article_url):
    try:
        resp = requests.get(article_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"Failed to retrieve article page: {article_url}")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        title_tag = soup.find('h1')
        title = clean_text(title_tag.text) if title_tag else ""

        time_tag = soup.find('div', class_='byline') or soup.find('span', class_='time_cptn')
        timestamp = clean_text(time_tag.text) if time_tag else ""

        article_body = soup.find('div', {"id": "articlebody"}) or soup.find('div', class_='article_content')
        if article_body:
            p = article_body.find('p')
            context = clean_text(p.text) if p else ""
        else:
            context = ""

        if "taylor swift" not in (title + context).lower():
            print(f"Skipping irrelevant article: {title}")
            return None

        uid = extract_uid_from_url(article_url)

        return {
            "title": title,
            "timestamp": timestamp,
            "uid": uid,
            "url": article_url,
            "context": context
        }

    except Exception as e:
        print(f"Error scraping article {article_url}: {e}")
        return None

def scrape_page(url):
    print(f"Scraping page: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        print(f"Failed to retrieve page: {url}")
        return [], None

    soup = BeautifulSoup(resp.text, 'html.parser')
    articles = []
    article_links = soup.find_all('a', href=True)
    
    for a in article_links:
        href = a['href']
        if "articleshow" in href and href.endswith(".cms"):
            full_url = href if href.startswith('http') else BASE_URL + href
            article_data = scrape_article_page(full_url)
            if article_data:
                articles.append(article_data)
                print(f"Scraped: {article_data['title']}")
            time.sleep(1)

    next_page = None
    pagination = soup.find('a', text=re.compile(r'Next|›', re.I))
    if pagination and 'href' in pagination.attrs:
        next_page = BASE_URL + pagination['href']

    return articles, next_page

def main():
    all_articles = []
    current_url = START_URL
    max_pages = 10
    pages_scraped = 0

    while current_url and pages_scraped < max_pages:
        articles, next_page = scrape_page(current_url)
        all_articles.extend(articles)

        if not next_page:
            print("No next page found, stopping.")
            break

        current_url = next_page
        pages_scraped += 1
        print(f"Completed page {pages_scraped}")

    print(f"\n✅ Done. Scraped {len(all_articles)} relevant articles.\n")

    # Output as JSON
    output_file = "taylor_swift_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=2, ensure_ascii=False)

    print(f"📝 Saved to: {output_file}")

if __name__ == "__main__":
    main()
