import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

BASE_URL = "https://www.deuxmoi.world"
SEARCH_KEYWORDS = ["taylor swift", "swift", "taylor"]
DATE_PATTERN = re.compile(r'([A-Z][a-z]+ \d{1,2}, \d{4})')
LOCATION_PATTERN = re.compile(r'\b(?:in|at|from|near|outside of)\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE)

articles = []

def get_soup(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
        else:
            print(f"Failed to retrieve page. Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def extract_posted_date(soup):
    time_tag = soup.find('time')
    if time_tag:
        if time_tag.get('datetime'):
            return time_tag['datetime']
        if time_tag.text:
            return time_tag.text.strip()

    for tag in soup.find_all(['meta', 'span', 'div', 'p']):
        text = tag.get_text(strip=True) if tag.name != 'meta' else tag.get('content', '')
        match = DATE_PATTERN.search(text)
        if match:
            return match.group(1)

    return "No date found"

def extract_location(text):
    matches = LOCATION_PATTERN.findall(text)
    if matches:
        return matches[0]  # Return the first likely location
    return "No location found"

def extract_article_data(article_url):
    soup = get_soup(article_url)
    if not soup:
        return

    title = soup.find('h1') or soup.find('h2')
    title_text = title.get_text(strip=True) if title else "No Title Found"

    date_posted = extract_posted_date(soup)

    # Description
    description = ""
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        description = meta['content']
    else:
        p_tag = soup.find('p')
        description = p_tag.get_text(strip=True) if p_tag else "No description found"

    location = extract_location(description)

    article_data = {
        "title": title_text,
        "date_posted": date_posted,
        "description": description,
        "location": location
    }

    articles.append(article_data)

    print(f"\n Title: {title_text}")
    print(f"Date Posted: {date_posted}")
    print(f"Location: {location}")
    print(f"Description: {description}")

def main():
    homepage_soup = get_soup(BASE_URL)
    if not homepage_soup:
        return

    links = homepage_soup.find_all('a', href=True)
    seen_links = set()

    print("\n Scanning homepage for Taylor Swift articles...\n")

    for link in links:
        href = link['href']
        text = link.get_text(strip=True).lower()
        href_lower = href.lower()

        if any(keyword in text or keyword in href_lower for keyword in SEARCH_KEYWORDS):
            full_url = href if href.startswith('http') else BASE_URL + href
            if full_url not in seen_links:
                seen_links.add(full_url)
                extract_article_data(full_url)

    # Save to JSON
    if articles:
        with open("taylor_swift_articles.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=4, ensure_ascii=False)
        print(f"\n Exported {len(articles)} articles to 'taylor_swift_articles.json'")
    else:
        print("\n No articles found to export.")

if __name__ == '__main__':
    main()