import json
import os
import time
import uuid
from datetime import datetime, timedelta

import psycopg2
import boto3
from botocore.exceptions import ClientError
from newsapi import NewsApiClient   

# ── Secrets ────────────────────────────────────────────────────────
AWS_REGION = "us-east-1"

def get_secret(secret_name: str, key: str | None = None) -> str | dict:
    """Return the whole secret as dict, or a single key if provided."""
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    try:
        secret_str = client.get_secret_value(SecretId=secret_name)["SecretString"]
    except ClientError as e:
        raise RuntimeError(f"Could not fetch secret {secret_name}: {e}") from e
    data = json.loads(secret_str)
    return data[key] if key else data

# ── DB helpers ─────────────────────────────────────────────────────
def get_db_conn():
    creds = get_secret("DB")  # returns dict with user, password, host, port, dbname
    return psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"],
    )

def setup_news_table():
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                uid         UUID PRIMARY KEY,
                title       TEXT,
                description TEXT,
                timestamp   TIMESTAMP
            );
        """)
        conn.commit()
    print(" news table ready.")

def insert_articles(articles: list[dict]):
    insert_sql = """
        INSERT INTO news (uid, title, description, timestamp)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (uid) DO NOTHING;
    """
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.executemany(insert_sql, [
            (
                str(art["uid"]),         # UUID → string
                art["title"],
                art["description"],
                art["timestamp"],
            )
            for art in articles
        ])
        conn.commit()
    print(f" Inserted {len(articles)} rows into news.")


def print_news_sample(limit: int = 5):
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT uid, title, timestamp
            FROM news
            ORDER BY timestamp DESC
            LIMIT %s;
        """, (limit,))
        rows = cur.fetchall()
    print(f"\n Latest {len(rows)} rows in news:")
    for r in rows:
        print(f" • {r[2]} — {r[1][:90]}…  (uid={r[0]})")

# ── NewsAPI config ────────────────────────────────────────────────
API_KEY       = get_secret("NEWS_API", "API_KEY")
QUERY         = '"Taylor Swift"'      # exact phrase
LANGUAGE      = "en"
PAGE_SIZE     = 100
REQUEST_DELAY = 1.0                   # seconds between requests
NUM_WINDOWS   = 10                    # split 30 days into windows

END   = datetime(2025, 6, 19)
START = END - timedelta(days=30)
DELTA = (END - START) / NUM_WINDOWS

def fetch_window(client, start_dt, end_dt):
    return client.get_everything(
        q=QUERY,
        language=LANGUAGE,
        sort_by="publishedAt",
        page_size=PAGE_SIZE,
        page=1,
        from_param=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        to=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    ).get("articles", [])

# ── Main flow ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) Prep DB
    setup_news_table()

    # 2) Fetch articles
    client = NewsApiClient(api_key=API_KEY)
    all_articles = []
    for i in range(NUM_WINDOWS):
        win_start = START + DELTA * i
        win_end   = win_start + DELTA
        print(f"[{i+1}/{NUM_WINDOWS}] {win_start:%Y-%m-%d} → {win_end:%Y-%m-%d}")
        window_articles = fetch_window(client, win_start, win_end)
        print(f"    fetched {len(window_articles)} articles")
        all_articles.extend(window_articles)
        time.sleep(REQUEST_DELAY)

    # 3) Dedupe by URL
    unique = list({a["url"]: a for a in all_articles}.values())
    print(f"After deduplication: {len(unique)} unique articles")

    # 4) Filter for exact phrase
    filtered = []
    for art in unique:
        combined = " ".join(
            (art.get("title") or "", art.get("description") or "", art.get("content") or "")
        ).lower()
        if "taylor swift" in combined:
            filtered.append(art)

    # 5) Project + generate uid
    projected = [{
        "uid":         uuid.uuid4(),
        "title":       art.get("title", ""),
        "description": art.get("description", ""),
        "timestamp":   art.get("publishedAt") or art.get("published_at") or datetime.utcnow().isoformat(),
    } for art in filtered]

    # 6) Persist JSON backup
    out_json = os.path.join(os.getcwd(), "taylor_swift_articles_30d.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump([{
            **art,
            "uid": str(art["uid"])
        } for art in projected], fp, ensure_ascii=False, indent=2)
    print(f"  Saved JSON → {out_json}")

    # 7) Insert into Postgres + show sample
    insert_articles(projected)
    print_news_sample(limit=10)