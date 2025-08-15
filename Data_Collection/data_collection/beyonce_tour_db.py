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

URL = "https://beyonce.com/tour"
now = datetime.now()
uid = f"beyonce_tour_{now.strftime('%Y%m%d_%H%M')}"

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
def create_beyonce_tours_table():
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
        CREATE TABLE IF NOT EXISTS beyonce_tours (
            uid TEXT,
            tour_date TEXT,
            city TEXT,
            scrape_time TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("beyonce_tours table ready.")

# ─── Insert Data ──────────────────────────────────────
def insert_beyonce_tours(shows):
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
        INSERT INTO beyonce_tours (uid, tour_date, city, scrape_time)
        VALUES (%s, %s, %s, %s);
    """
    for show in shows:
        cur.execute(insert_query, (
            show["uid"],
            show["date"],
            show["city"],
            show["scrape_time"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(shows)} Beyoncé tour events into beyonce_tours.")

# ─── Scrape and Parse ─────────────────────────────────
def scrape_beyonce_tour_dates():
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

    for block in soup.select("a.tour-date"):
        divs = block.select("div.mb-1")
        if len(divs) >= 2:
            date = divs[0].get_text(strip=True)
            city = divs[1].get_text(strip=True)
            shows.append({
                "uid": uid,
                "date": date,
                "city": city,
                "scrape_time": now
            })

    return shows

# ─── Main ─────────────────────────────────────────────
if __name__ == "__main__":
    tour_dates = scrape_beyonce_tour_dates()
    create_beyonce_tours_table()
    insert_beyonce_tours(tour_dates)