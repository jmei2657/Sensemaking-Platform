
#Don't use apparently there's not a enought data from this

import requests
from bs4 import BeautifulSoup
import spacy
import json
import re
import uuid
from datetime import datetime
import boto3
import psycopg2
from botocore.exceptions import ClientError

# ── AWS Secrets ─────────────────────────────────────────────
AWS_REGION = "us-east-1"

def get_secret(secret_name: str, key: str = None) -> str | dict:
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    try:
        secret_str = client.get_secret_value(SecretId=secret_name)["SecretString"]
        secret = json.loads(secret_str)
        return secret[key] if key else secret
    except ClientError as e:
        raise RuntimeError(f"Unable to get secret {secret_name}: {e}")

# ── DB Connection ───────────────────────────────────────────
def get_db_conn():
    creds = get_secret("DB")
    return psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"],
    )

# ── Create Table ────────────────────────────────────────────
def setup_table():
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS taylorfanforum (
            uid         UUID PRIMARY KEY,
            thread      TEXT,
            date        TIMESTAMP,
            text        TEXT,
            locations   TEXT[],
            events      TEXT[]
        );
        """)
        conn.commit()
    print(" taylorfanforum table ready.")

# ── Insert Posts ─────────────────────────────────────────────
def insert_posts(posts: list[dict]):
    insert_sql = """
    INSERT INTO taylorfanforum (uid, thread, date, text, locations, events)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (uid) DO NOTHING;
    """
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.executemany(insert_sql, [
            (
                str(uuid.uuid4()),
                post["thread"],
                parse_date(post["date"]),
                post["text"],
                post["locations"],
                post["events"]
            )
            for post in posts
        ])
        conn.commit()
    print(f" Inserted {len(posts)} posts into taylorfanforum.")

def parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%b %d, %Y")
    except:
        return datetime.utcnow()

# ── Scraper Logic ────────────────────────────────────────────
FORUM_URL = "https://thetaylorswiftsociety.com/feed"
BASE_URL = "https://www.thetaylorswift"
HEADERS = {"User-Agent": "Mozilla/5.0"}

nlp = spacy.load("en_core_web_sm")

def extract_locations(text):
    doc = nlp(text)
    return list({ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")})

def extract_events(text):
    return [
        sent.text.strip()
        for sent in nlp(text).sents
        if re.search(r"\b(concert|tour|show|ticket)\b", sent.text, re.IGNORECASE)
    ]

def parse_thread_post(thread_url):
    resp = requests.get(thread_url, headers=HEADERS)
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    posts = soup.select("div.message")
    data = []

    for post in posts[:3]:
        content = post.select_one("div.messageText")
        timestamp = post.find("span", class_="muted")
        text = content.get_text(separator=" ", strip=True) if content else ""
        date = timestamp.get_text(strip=True) if timestamp else None

        if "taylor swift" not in text.lower():
            continue

        locations = extract_locations(text)
        events = extract_events(text)

        data.append({
            "thread": thread_url,
            "date": date,
            "text": text[:300] + "...",
            "locations": locations,
            "events": events
        })

    return data

def fetch_recent_threads():
    resp = requests.get(FORUM_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    threads = soup.select("a.title[href*='/t/']")
    urls = [BASE_URL + a["href"] for a in threads[:5]]
    return urls

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    setup_table()
    results = []

    for thread_url in fetch_recent_threads():
        results.extend(parse_thread_post(thread_url))

    with open("fanforum_taylor_swift.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    insert_posts(results)
    print(f"\n Scraped + saved {len(results)} posts from fan forum.")
