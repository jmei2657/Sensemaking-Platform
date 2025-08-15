from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import json
import psycopg2
import boto3
from botocore.exceptions import ClientError

# ─── CONFIG ───────────────────────────────────────────
AWS_REGION = "us-east-1"
DB_SECRET_NAME = "DB"

url = "https://www.tmz.com/people/sza/"
now = datetime.now()
scrape_time = now.strftime('%Y-%m-%d %H:%M:%S')
uid = f"tmz_sza_{now.strftime('%Y%m%d_%H%M')}"
filename = f"{uid}.json"
log_file = "scrape_log.txt"

# ─── AWS Secrets Manager ──────────────────────────────
def get_secret(secret_name=DB_SECRET_NAME, region_name=AWS_REGION):
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        print(" Failed to get secret:", e)
        raise e

# ─── Create TMZ Table ─────────────────────────────────
def create_tmz_table():
    creds = get_secret()
    conn = psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"]
    )
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tmz_sza (
            uid TEXT,
            title TEXT,
            published_date TIMESTAMP,
            excerpt TEXT,
            scrape_time TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print(" TMZ table ready.")

# ─── Insert Data ──────────────────────────────────────
def insert_tmz_articles(articles):
    creds = get_secret()
    conn = psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"]
    )
    cur = conn.cursor()
    insert_query = """
        INSERT INTO tmz_sza (uid, title, published_date, excerpt, scrape_time)
        VALUES (%s, %s, %s, %s, %s);
    """
    for art in articles:
        cur.execute(insert_query, (
            art["uid"],
            art["title"],
            art["published_date"],
            art["excerpt"],
            art["scrape_time"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f" Inserted {len(articles)} articles into TMZ table.")

# ─── Scrape HTML ──────────────────────────────────────
def scrape_tmz():
    print(f" Scraping {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(7000)  # wait for JS content to load
        html = page.content()
        browser.close()
    return html

# ─── Parse and Extract ────────────────────────────────
def parse_articles(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="gridler__card-description gridler__card-description--default")
    articles = []

    for card in cards:
        # Title
        headline_tag = card.find_previous("h3", class_="gridler__card-title gridler__card-title--default")
        headline = headline_tag.get_text(strip=True) if headline_tag else "No title"

        # Date → convert to TIMESTAMP
        date_tag = headline_tag.find_previous("span", class_="gridler__media-date gridler__media-date--default") if headline_tag else None
        date_str = date_tag.get_text(strip=True).replace("Published: ", "") if date_tag else None
        try:
            published_date = datetime.strptime(date_str, "%b %d, %Y")
        except:
            published_date = now  # fallback

        # Excerpt
        desc_div = card.find("div", class_="description-text")
        excerpt = desc_div.get_text(strip=True) if desc_div else "No excerpt"

        # Store structured article
        articles.append({
            "title": headline,
            "published_date": published_date,
            "excerpt": excerpt,
            "scrape_time": now,
            "uid": uid
        })

    return articles

# ─── Main Entry ───────────────────────────────────────
if __name__ == "__main__":
    html = scrape_tmz()
    articles = parse_articles(html)

    # Save backup JSON
    with open(filename, "w", encoding="utf-8") as f:
        json.dump([{
            **art,
            "published_date": art["published_date"].isoformat(),
            "scrape_time": art["scrape_time"].isoformat()
        } for art in articles], f, indent=2, ensure_ascii=False)
    print(f" Saved to {filename}")

    # Log scrape
    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"{now.strftime('%Y-%m-%d %H:%M:%S')} | UID: {uid} | Articles scraped: {len(articles)}\n")

    # Create table + insert
    create_tmz_table()
    insert_tmz_articles(articles)