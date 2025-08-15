# scripts/api/fetch_taylor_swift_windows.py

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from newsapi import NewsApiClient

import boto3
from botocore.exceptions import ClientError

def get_secret():
    secret_name = "NEWS_API"
    region_name = "us-east-1"

    # Create a Secrets Manager client (Boto3)
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # See get_secret_value API Reference for possible exceptions :contentReference[oaicite:1]{index=1}
        raise e

    # Secrets Manager returns a JSON string; parse and extract "API_KEY"
    secret_json = response['SecretString']
    return json.loads(secret_json)["API_KEY"]  # use uppercase key name

# ─── Configuration ────────────────────────────────────────────────
API_KEY       = get_secret()
QUERY         = '"Taylor Swift"'   # exact-phrase match in full body
LANGUAGE      = "en"
PAGE_SIZE     = 100
REQUEST_DELAY = 1.0                # seconds between requests
NUM_WINDOWS   = 10                  # split the last 30 days into 7 windows

# ─── Compute Windows ───────────────────────────────────────────────
END   = datetime(2025, 6, 19)               # inclusive end date
START = END - timedelta(days=30)            # 30 days before
DELTA = (END - START) / NUM_WINDOWS         # length of each window

# ─── Helper to fetch one window ────────────────────────────────────
def fetch_window(client, start_dt, end_dt):
    # ensure no microseconds creep in
    from_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    to_str   = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

    resp = client.get_everything(
        q=QUERY,
        language=LANGUAGE,
        sort_by="publishedAt",
        page_size=PAGE_SIZE,
        page=1,
        from_param=from_str,
        to=to_str,
    )
    return resp.get("articles", [])
# ─── Main Script ──────────────────────────────────────────────────
if __name__ == "__main__":
    client = NewsApiClient(api_key=API_KEY)
    raw_articles = []

    # 1) Fetch each of the 7 windows
    for i in range(NUM_WINDOWS):
        win_start = START + DELTA * i
        win_end   = win_start + DELTA
        print(f"[INFO] Window {i+1}/{NUM_WINDOWS}: {win_start.date()} → {win_end.date()}")

        window_articles = fetch_window(client, win_start, win_end)
        print(f"       Fetched {len(window_articles)} raw articles")
        raw_articles.extend(window_articles)

        time.sleep(REQUEST_DELAY)

    # 2) Deduplicate by URL
    unique = list({a["url"]: a for a in raw_articles}.values())
    print(f"[INFO] After dedupe: {len(unique)} unique articles")

    # 3) Filter to ensure the exact phrase appears somewhere
    filtered = []
    for art in unique:
        # pull the three fields, coalescing None → ""
        parts = [
            art.get("title"),
            art.get("description"),
            art.get("content"),
        ]
        text = " ".join([p or "" for p in parts]).lower()

        if "taylor swift" in text:
            filtered.append(art)

    # 4) Project only needed fields + generate uid
    projected = [{
        "uid":       str(uuid.uuid4()),
        "title":     art.get("title", ""),
        "description": art.get("description", ""),
        "timestamp": art.get("publishedAt", ""),
    } for art in filtered]

    # 5) Save to JSON
    out_path = os.path.join(os.getcwd(), "taylor_swift_articles_30d2.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(projected, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(projected)} articles to {out_path}")
