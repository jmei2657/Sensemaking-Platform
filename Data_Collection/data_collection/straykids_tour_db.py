from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import json
import psycopg2
import boto3
from botocore.exceptions import ClientError
import time

# ─── CONFIG ───────────────────────────────────────────
AWS_REGION = "us-east-1"
DB_SECRET_NAME = "DB"

URL = "https://detour.songkick.com/artists/9574724-stray-kids/calendar"
now = datetime.now()
uid = f"straykids_tour_{now.strftime('%Y%m%d_%H%M')}"

# ─── AWS Secrets Manager ──────────────────────────────
def get_secret(secret_name=DB_SECRET_NAME, region_name=AWS_REGION):
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        print("Failed to get secret:", e)
        raise e

# ─── Create Table ─────────────────────────────────────
def create_straykids_tours_table():
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
        CREATE TABLE IF NOT EXISTS straykids_tours (
            uid TEXT,
            tour_date TEXT,
            location TEXT,
            scrape_time TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("straykids_tours table ready.")

# ─── Insert Data ──────────────────────────────────────
def insert_straykids_tours(events):
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
        INSERT INTO straykids_tours (uid, tour_date, location, scrape_time)
        VALUES (%s, %s, %s, %s);
    """
    for event in events:
        cur.execute(insert_query, (
            event["uid"],
            event["date"],
            event["location"],
            event["scrape_time"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(events)} tour events into straykids_tours.")

# ─── Scrape and Parse ─────────────────────────────────
def scrape_straykids_tour():
    print(f"Scraping: {URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        time.sleep(5)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    shows = []

    for li in soup.select("li.event-listing[title]"):
        date = li.get("title", "").strip()
        link = li.select_one("a")

        if date and link:
            location_text = " ".join(link.stripped_strings)
            shows.append({
                "uid": uid,
                "date": date,
                "location": location_text,
                "scrape_time": now
            })

    return shows

# ─── Main ─────────────────────────────────────────────
if __name__ == "__main__":
    events = scrape_straykids_tour()
    create_straykids_tours_table()
    insert_straykids_tours(events)