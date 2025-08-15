
#I ran this and it didn't scrape anything
#this is blank table rn, can maybe get rid of this source

import requests
from bs4 import BeautifulSoup
import re
import spacy
import json
import uuid
from datetime import datetime
import psycopg2
import boto3
from botocore.exceptions import ClientError

# ── Secrets ────────────────────────────────────────────────────────
AWS_REGION = "us-east-1"

def get_secret(secret_name: str, key: str | None = None) -> str | dict:
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    try:
        secret_str = client.get_secret_value(SecretId=secret_name)["SecretString"]
    except ClientError as e:
        raise RuntimeError(f"Could not fetch secret {secret_name}: {e}") from e
    data = json.loads(secret_str)
    return data[key] if key else data

# ── DB helpers ─────────────────────────────────────────────────────
def get_db_conn():
    creds = get_secret("DB")
    return psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"],
    )

def setup_dailymail_table():
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dailymail (
                uid         UUID PRIMARY KEY,
                title       TEXT,
                date_posted TIMESTAMP,
                location    TEXT[],
                description TEXT
            );
        """)
        conn.commit()
    print(" dailymail table ready.")

def insert_articles(articles: list[dict]):
    insert_sql = """
        INSERT INTO dailymail (uid, title, date_posted, location, description)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (uid) DO NOTHING;
    """
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.executemany(insert_sql, [
            (
                art["uid"],
                art["title"],
                art["date_posted"],
                art["location"],
                art["description"],
            )
            for art in articles
        ])
        conn.commit()
    print(f" Inserted {len(articles)} rows into dailymail.")

# ── Scraping logic ─────────────────────────────────────────────———
BASE_URL = "https://www.dailymail.co.uk/tvshowbiz/taylor_swift/index.html"
DATE_PATTERN = re.compile(r'([A-Z][a-z]+ \d{1,2}, \d{4})')
nlp = spacy.load("en_core_web_sm")


def get_soup(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f" Error fetching {url}: {e}")
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
    return None

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%B %d, %Y")
    except Exception:
        return None

def extract_geo_locations(text):
    doc = nlp(text)
    return list({ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")})

def extract_article_data(article_url):
    soup = get_soup(article_url)
    if not soup:
        return None

    title_tag = soup.find('h1') or soup.find('h2')
    title = title_tag.get_text(strip=True) if title_tag else "No Title Found"
    if "taylor swift" not in title.lower():
        return None

    raw_date = extract_posted_date(soup)
    date_posted = parse_date(raw_date) if raw_date else datetime.utcnow()

    meta = soup.find('meta', attrs={'name': 'description'})
    description = meta['content'] if meta and meta.get('content') else ""
    if not description or "taylor swift" not in description.lower():
        return None

    paragraphs = soup.find_all('p')
    full_text = " ".join(p.get_text(strip=True) for p in paragraphs)
    locations = extract_geo_locations(full_text)

    return {
        "uid": uuid.uuid4(),
        "title": title,
        "date_posted": date_posted,
        "location": locations,
        "description": description
    }

# ── Main script ─────────────────────────────────────────────────———
def main():
    setup_dailymail_table()
    homepage = get_soup(BASE_URL)
    if not homepage:
        return

    seen_links = set()
    links = homepage.find_all('a', href=True)
    articles = []

    print("\n Scanning Daily Mail homepage for Taylor Swift articles...")
    for link in links:
        href = link['href'].strip()
        full_url = href if href.startswith('http') else "https://www.dailymail.co.uk" + href

        if "/taylor-swift/" in full_url and full_url not in seen_links:
            seen_links.add(full_url)
            article = extract_article_data(full_url)
            if article:
                print(f" Article: {article['title']}")
                articles.append(article)

    if articles:
        insert_articles(articles)
    else:
        print(" No valid Taylor Swift articles found.")

if __name__ == '__main__':
    main()