#!/usr/bin/env python3
"""
Scrape The Guardian's SZA music page, store into Postgres guardian_beyonce table.

Table schema (created if missing):

CREATE TABLE guardian_beyonce (
    url TEXT PRIMARY KEY,
    uid TEXT,
    date_timestamp TIMESTAMP,
    meta_data TEXT,
    title_context TEXT
);
"""

import re
import json
import hashlib
from datetime import datetime
from pathlib import Path

import boto3
import psycopg2
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ───────────────────────── CONFIG ─────────────────────────
AWS_REGION   = "us-east-1"
DB_SECRET    = "DB"
START_URL    = "https://www.theguardian.com/music/beyonce"
BASE_URL     = "https://www.theguardian.com"
HEADLESS     = True
WAIT_MS      = 4_000
MAX_PAGES    = 1000
CUTOFF_DATE = datetime(2024, 4, 18)
# ───────────────────────────────────────────────────────────

def get_db_creds():
    session = boto3.session.Session()
    client  = session.client("secretsmanager", region_name=AWS_REGION)
    try:
        secret = client.get_secret_value(SecretId=DB_SECRET)["SecretString"]
    except ClientError as e:
        raise RuntimeError(f"SecretsManager error: {e}")
    return json.loads(secret)

def create_guardian_table():
    creds = get_db_creds()
    with psycopg2.connect(**{
        "dbname": creds["dbname"], "user": creds["user"], "password": creds["password"],
        "host": creds["host"], "port": creds["port"]
    }) as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guardian_beyonce (
                url TEXT PRIMARY KEY,
                uid TEXT,
                date_timestamp TIMESTAMP,
                meta_data TEXT,
                title_context TEXT
            );
        """)
        conn.commit()
    print(" guardian table ready.")

def insert_guardian_rows(rows: list[dict]):
    creds = get_db_creds()
    with psycopg2.connect(**{
        "dbname": creds["dbname"], "user": creds["user"], "password": creds["password"],
        "host": creds["host"], "port": creds["port"]
    }) as conn, conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO guardian_beyonce (url, uid, date_timestamp, meta_data, title_context)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING;
        """, [
            (
                art["url"],
                art["uid"],
                art["date_timestamp"],
                art["meta_data"],
                art["title_context"]
            ) for art in rows
        ])
        conn.commit()
    print(f" Inserted {len(rows)} rows into guardian_beyonce.")

def parse_date_from_url(url: str) -> datetime | None:
    patterns = [
        r'/(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{1,2})/',
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/'
    ]
    month_map = {m: i+1 for i, m in enumerate(
        ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}

    for pat in patterns:
        m = re.search(pat, url.lower())
        if m:
            y, mo, d = m.groups()
            mo = int(mo) if mo.isdigit() else month_map.get(mo, 1)
            try:
                return datetime(int(y), mo, int(d))
            except ValueError:
                return None
    return None

def get_article_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()

        if "sza" in text or "sza" in href:
            if href.startswith("/"):
                href = BASE_URL + href
            elif not href.startswith("http"):
                href = BASE_URL + "/" + href
            links.add(href.split("?")[0])
    return list(links)

def scrape_article(page, url: str) -> dict:
    page.goto(url)
    page.wait_for_timeout(3_000)
    soup = BeautifulSoup(page.content(), "html.parser")

    title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Untitled"

    body_div = soup.find("div", {"data-gu-name": "body"})
    body_text = " ".join(p.get_text(strip=True) for p in body_div.find_all("p")) if body_div else ""
    
    if "sza" not in body_text.lower():
        raise ValueError("Irrelevant article (Beyonce not mentioned)")
    
    body_text = body_text[:600] + ("…" if len(body_text) > 600 else "")

    meta_date = soup.find("time").get("datetime") if soup.find("time") else "N/A"

    url_dt = parse_date_from_url(url) or datetime.utcnow()

    return {
        "url": url,
        "uid": hashlib.md5(url.encode()).hexdigest(),
        "date_timestamp": url_dt,
        "meta_data": meta_date,
        "title_context": f"{title} — {body_text}"
    }

def crawl_guardian():
    all_rows, seen = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page    = browser.new_page()

        page_num, empty_chain = 1, 0
        while page_num <= MAX_PAGES:
            target = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f" Page {page_num}: {target}")
            page.goto(target)
            page.wait_for_timeout(WAIT_MS)
            html = page.content()

            links = [l for l in get_article_links(html) if l not in seen]
            if not links:
                empty_chain += 1
                if empty_chain >= 3:
                    break
                page_num += 1
                continue
            empty_chain = 0

            for link in links:
                try:
                    art = scrape_article(page, link)

                    if art["date_timestamp"] < CUTOFF_DATE:
                        print(f"    stopping: article is older than cutoff ({art['date_timestamp'].date()})")
                        browser.close()
                        return all_rows

                    all_rows.append(art)
                    seen.add(link)
                    print(f"   + {art['title_context'][:70]}…")
                except Exception as e:
                    print(f"    scrape error {link}: {e}")

            page_num += 1

        browser.close()
    return all_rows

if __name__ == "__main__":
    rows = crawl_guardian()
    print(f"\n Total unique articles: {len(rows)}")

    create_guardian_table()
    insert_guardian_rows(rows)