from bs4 import BeautifulSoup
from datetime import datetime
import json
import psycopg2
import boto3
from botocore.exceptions import ClientError
import requests
import pandas as pd

# ─── CONFIG ───────────────────────────────────────────
AWS_REGION = "us-east-1"
DB_SECRET_NAME = "DB"

url = "https://www.azcentral.com/story/entertainment/music/2023/03/23/taylor-swift-eras-tour-2023-locations/70031117007/"
now = datetime.now()
scrape_time = now.strftime('%Y-%m-%d %H:%M:%S')
uid = f"taylor_tour_{now.strftime('%Y%m%d_%H%M')}"
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
        print("Failed to get secret:", e)
        raise e

# ─── Create Taylor Tour Table ─────────────────────────
def create_taylor_tours_table():
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
        CREATE TABLE IF NOT EXISTS taylor_tours (
            uid TEXT,
            tour_date TEXT,
            venue_location TEXT,
            scrape_time TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("taylor_tours table ready.")

# ─── Insert Data ──────────────────────────────────────
def insert_taylor_tours(entries):
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
        INSERT INTO taylor_tours (uid, tour_date, venue_location, scrape_time)
        VALUES (%s, %s, %s, %s);
    """
    for entry in entries:
        cur.execute(insert_query, (
            entry["uid"],
            entry["date"],
            entry["venue_location"],
            entry["scrape_time"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(entries)} tour dates into taylor_tours.")

# ─── Scrape Tour Dates ───────────────────────────────
def scrape_tour_dates_table(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    tour_dates = []

    # Try to find tables
    tables = soup.find_all('table')
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if any('date' in h for h in headers) and any('location' in h for h in headers):
            for row in table.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 2:
                    date = cols[0].get_text(strip=True)
                    location = cols[1].get_text(strip=True)
                    tour_dates.append({'date': date, 'venue_location': location})
            if tour_dates:
                break

    # Fallback: parse unordered lists
    if not tour_dates:
        lists = soup.find_all('ul')
        for ul in lists:
            for li in ul.find_all('li'):
                text = li.get_text(separator=' ', strip=True)
                if any(month in text for month in
                       ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                    tour_dates.append({'date_location': text})

    return tour_dates

# ─── Main Entry ───────────────────────────────────────
if __name__ == "__main__":
    raw_dates = scrape_tour_dates_table(url)

    # Normalize and structure
    structured = []
    for item in raw_dates:
        if 'date' in item and 'venue_location' in item:
            structured.append({
                "uid": uid,
                "date": item["date"],
                "venue_location": item["venue_location"],
                "scrape_time": now
            })
        elif 'date_location' in item:
            structured.append({
                "uid": uid,
                "date": None,
                "venue_location": item["date_location"],
                "scrape_time": now
            })

    # Save backup JSON
    with open(filename, "w", encoding="utf-8") as f:
        json.dump([{
            **row,
            "scrape_time": row["scrape_time"].isoformat()
        } for row in structured], f, indent=2)
    print(f"Saved to {filename}")

    # Log scrape
    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"{scrape_time} | UID: {uid} | Entries scraped: {len(structured)}\n")

    # Store to DB
    create_taylor_tours_table()
    insert_taylor_tours(structured)