import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import psycopg2
import boto3
from botocore.exceptions import ClientError

# ---------- AWS + DB CONFIG ----------
AWS_REGION     = "us-east-1"
DB_SECRET_NAME = "DB"
URL = "https://szatour.info/"

# ---------- AWS Secrets ----------
def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print("Failed to get secret:", e)
        raise e

# ---------- DB Setup ----------
def setup_db():
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sza_tours (
            id SERIAL PRIMARY KEY,
            title TEXT,
            date TEXT,
            location TEXT
        );
    """)
    conn.commit()
    print("Table 'sza_tours' ready.")
    cur.close()
    conn.close()

# ---------- Scraping ----------
def scrape_tours(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ScraperBot/1.0)"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    tours = []
    dates = soup.select('div.date[data-date]')
    data_date_list = [d['data-date'] for d in dates]
    blocks = soup.select('.cover-block')

    for i, block in enumerate(blocks):
        link_tag = block.select_one('.cover-link')
        title = link_tag['href'] if link_tag else 'No title'

        raw_date = data_date_list[i] if i < len(data_date_list) else None
        try:
            full_date = datetime.fromisoformat(raw_date).strftime('%b %d, %Y')
        except:
            full_date = None

        loc_tag = block.select_one('.date-name')
        location = loc_tag.get_text(strip=True) if loc_tag else 'No location'

        tours.append({
            'title': title,
            'date': full_date,
            'location': location
        })

    return tours

# ---------- Insert Into DB ----------
def insert_tours(tours):
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()

    insert_query = """
        INSERT INTO sza_tours (title, date, location)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    for tour in tours:
        cur.execute(insert_query, (tour['title'], tour['date'], tour['location']))
    conn.commit()
    print(f"Inserted {len(tours)} tour dates into 'sza_tours'.")

    cur.close()
    conn.close()

# ---------- Print Tour Table ----------
def print_sza_tours_table(limit=10):
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, date, location FROM sza_tours
        ORDER BY date ASC
        LIMIT %s;
    """, (limit,))

    rows = cur.fetchall()

    print(f"\nShowing {len(rows)} tour entries from 'sza_tours':\n")
    for row in rows:
        print(f"ID: {row[0]}\nTitle: {row[1]}\nDate: {row[2]}\nLocation: {row[3]}\n{'-'*40}")

    cur.close()
    conn.close()

# ---------- Main ----------
def main():
    setup_db()
    tours = scrape_tours(URL)
    insert_tours(tours)
    print_sza_tours_table(limit=20)

if __name__ == "__main__":
    main()