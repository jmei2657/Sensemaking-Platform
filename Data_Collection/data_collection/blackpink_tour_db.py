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

URL = "https://www.kpoppost.com/blackpink-world-tour-2025-complete-dates-schedule-comeback-prediction/"
now = datetime.now()
uid = f"blackpink_tour_{now.strftime('%Y%m%d_%H%M')}"

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
def create_blackpink_tours_table():
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
        CREATE TABLE IF NOT EXISTS blackpink_tours (
            uid TEXT,
            tour_date TEXT,
            venue TEXT,
            region TEXT,
            scrape_time TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("blackpink_tours table ready.")

# ─── Insert Data ──────────────────────────────────────
def insert_blackpink_tours(tour_data):
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
        INSERT INTO blackpink_tours (uid, tour_date, venue, region, scrape_time)
        VALUES (%s, %s, %s, %s, %s);
    """
    for event in tour_data:
        cur.execute(insert_query, (
            event["uid"],
            event["date"],
            event["venue"],
            event["region"],
            event["scrape_time"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(tour_data)} tour events into blackpink_tours.")

# ─── Scrape and Parse ─────────────────────────────────
def get_tour_dates():
    print(f"Scraping: {URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    tour_data = []
    current_region = None

    for tag in soup.find_all(['h4', 'p']):
        if tag.name == 'h4' and 'wp-block-heading' in tag.get('class', []):
            current_region = tag.get_text(strip=True)
        elif tag.name == 'p':
            parts = list(tag.stripped_strings)
            if len(parts) >= 2:
                venue_line = parts[0]
                date_line = parts[1]

                tour_data.append({
                    "uid": uid,
                    "date": date_line,
                    "venue": venue_line,
                    "region": current_region,
                    "scrape_time": now
                })

    return tour_data

# ─── Main ─────────────────────────────────────────────
if __name__ == "__main__":
    tour = get_tour_dates()
    create_blackpink_tours_table()
    insert_blackpink_tours(tour)