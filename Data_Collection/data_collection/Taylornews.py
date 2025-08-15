import requests
from bs4 import BeautifulSoup
import re
import json
import spacy

BASE_URL = "https://www.dailymail.co.uk/tvshowbiz/taylor_swift/index.html"
SEARCH_KEYWORDS = ["taylor swift"]
articles = []

# Compile patterns
DATE_PATTERN = re.compile(r'([A-Z][a-z]+ \d{1,2}, \d{4})')

# Load spaCy for accurate location extraction
nlp = spacy.load("en_core_web_sm")

def get_soup(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
        else:
            print(f"❌ Failed to retrieve page. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
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

def extract_geo_locations(text):
    doc = nlp(text)
    return list({ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")})

def extract_article_data(article_url):
    soup = get_soup(article_url)
    if not soup:
        return

    title_tag = soup.find('h1') or soup.find('h2')
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

    if "taylor swift" not in title.lower():
        return  # Skip unrelated articles

    date_posted = extract_posted_date(soup)

    # Extract article summary
    meta = soup.find('meta', attrs={'name': 'description'})
    description = meta['content'] if meta and meta.get('content') else ""

    if not description or "taylor swift" not in description.lower():
        return  # Skip if Taylor Swift isn't mentioned

    # Full article text
    paragraphs = soup.find_all('p')
    article_text = " ".join(p.get_text(strip=True) for p in paragraphs)

    # Extract only geographical locations
    locations = extract_geo_locations(article_text)

    article_data = {
        "title": title,
        "date_posted": date_posted,
        "location": locations,
        "description": description
    }

    articles.append(article_data)

    print(f"\n📰 Title: {title}")
    print(f"📅 Date Posted: {date_posted}")
    print(f"📍 Locations: {locations}")
    print(f"📝 Description: {description}")

def main():
    homepage_soup = get_soup(BASE_URL)
    if not homepage_soup:
        return

    links = homepage_soup.find_all('a', href=True)
    seen_links = set()

    print("\n🔍 Scanning homepage for Taylor Swift articles...\n")

    for link in links:
        href = link['href'].strip()
        full_url = href if href.startswith('http') else "https://www.dailymail.co.uk" + href

        # Must stay on DailyMail and mention Taylor Swift in the URL
        if "dailymail.co.uk" in full_url and "/taylor-swift/" in full_url and full_url not in seen_links:
            seen_links.add(full_url)
            extract_article_data(full_url)

    if articles:
        with open("taylor_swift_dailymail.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Exported {len(articles)} articles to 'taylor_swift_dailymail.json'")
    else:
        print("\n⚠️ No valid Taylor Swift articles found.")

if __name__ == '__main__':
    main()