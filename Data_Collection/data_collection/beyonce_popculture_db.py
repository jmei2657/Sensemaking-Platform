import boto3
import json
import praw
import psycopg2
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# ---------- CONFIGURATION ----------
AWS_REGION     = "us-east-1"
DB_SECRET_NAME = "DB"
REDDIT_SECRET  = "reddit_api_credentials"
SUBREDDIT      = "popculturechat"
SEARCH_QUERY   = "beyonce"
CUTOFF_DATE    = datetime(2024, 4, 18, tzinfo=timezone.utc)
SLEEP_SECONDS  = 2
# -----------------------------------

def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print(" Failed to get secret:", e)
        raise e

def setup_database():
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()

    print(" Connected to database.")

    create_table_query = """
        CREATE TABLE IF NOT EXISTS popculture_reddit_beyonce (
            id TEXT PRIMARY KEY,
            title TEXT,
            subreddit TEXT,
            created_utc TIMESTAMP,
            num_comments INTEGER,
            selftext TEXT,
            locked BOOLEAN,
            is_original_content BOOLEAN,
            upvote_ratio FLOAT
        );
        """
    cur.execute(create_table_query)
    conn.commit()
    print(" Reddit table created or verified.")

    cur.execute("SELECT COUNT(*) FROM popculture_reddit_beyonce;")
    count = cur.fetchone()[0]
    print(f" Existing posts in DB: {count}")

    cur.close()
    conn.close()

def connect_to_reddit() -> praw.Reddit:
    creds = get_secret(REDDIT_SECRET)
    print(" Connected to Reddit API.")
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        user_agent=creds["user_agent"],
    )

def collect_and_insert_every_10(reddit: praw.Reddit, subreddit_name: str, cutoff_dt: datetime):
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
        INSERT INTO popculture_reddit_beyonce (
            id, title, subreddit, created_utc, num_comments,
            selftext, locked, is_original_content, upvote_ratio
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """

    cutoff_ts = cutoff_dt.timestamp()
    subreddit = reddit.subreddit(subreddit_name)
    post_batch = []
    total_collected = 0

    print(f" Searching r/{subreddit_name} for '{SEARCH_QUERY}' posts since {cutoff_dt.date()}...")

    for submission in subreddit.search(SEARCH_QUERY, sort="new", time_filter="year", limit=1000):
        if submission.created_utc < cutoff_ts:
            continue

        post = {
            "id": submission.id,
            "title": submission.title,
            "subreddit": str(submission.subreddit),
            "created_utc": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
            "num_comments": submission.num_comments,
            "selftext": getattr(submission, "selftext", ""),
            "locked": submission.locked,
            "is_original_content": submission.is_original_content,
            "upvote_ratio": submission.upvote_ratio,
        }
        post_batch.append(post)
        total_collected += 1
        print(f" Collected {total_collected} posts...")

        if len(post_batch) == 10:
            for post in post_batch:
                cur.execute(insert_query, (
                    post["id"], post["title"], post["subreddit"], post["created_utc"],
                    post["num_comments"], post["selftext"], post["locked"],
                    post["is_original_content"], post["upvote_ratio"]
                ))
            conn.commit()
            print(" Inserted batch of 10 posts.")
            post_batch = []

        time.sleep(SLEEP_SECONDS)

    if post_batch:
        for post in post_batch:
            cur.execute(insert_query, (
                post["id"], post["title"], post["subreddit"], post["created_utc"],
                post["num_comments"], post["selftext"], post["locked"],
                post["is_original_content"], post["upvote_ratio"]
            ))
        conn.commit()
        print(f" Inserted final batch of {len(post_batch)} posts.")

    cur.close()
    conn.close()
    print(f" ✅ Finished: Inserted {total_collected} posts.")

def print_reddit_table(limit=10):
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
        SELECT id, title, subreddit, created_utc, num_comments, locked, is_original_content, upvote_ratio
        FROM popculture_reddit_beyonce ORDER BY created_utc DESC LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()

    print(f"\n Showing {len(rows)} most recent posts from 'popculture_reddit_beyonce' table:")
    for row in rows:
        print(f"""
        ID: {row[0]}
        Title: {row[1][:80]}...
        Subreddit: {row[2]}
        Created UTC: {row[3]}
        # Comments: {row[4]}
        Locked: {row[5]}
        OC: {row[6]}
        Upvote Ratio: {row[7]}
        """)

    cur.close()
    conn.close()

def main():
    setup_database()
    reddit = connect_to_reddit()
    collect_and_insert_every_10(reddit, SUBREDDIT, CUTOFF_DATE)
    print_reddit_table(limit=10)

if __name__ == "__main__":
    main()