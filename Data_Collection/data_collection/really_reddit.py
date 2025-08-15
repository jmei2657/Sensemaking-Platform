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
SUBREDDIT      = "beyonce"

SUBREDDITS     = ["beyonce","sza","TaylorSwift","straykids","BlackPink"]
DB_TABLE_NAMES = ["reddit_beyonce","reddit_sza","reddit_taylor","reddit_straykids","reddit_blackpink"]

CUTOFF_DATE    = datetime(2024, 4, 18, tzinfo=timezone.utc)
SLEEP_SECONDS  = 2
# -----------------------------------

# ---------------------- Secrets ----------------------
def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print(" Failed to get secret:", e)
        raise e

# ---------------------- DB Setup ----------------------
def setup_database(db_table):
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

    create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {db_table} (
            id TEXT PRIMARY KEY,
            title TEXT,
            subreddit TEXT,
            created_utc TIMESTAMP,
            num_comments INTEGER,
            selftext TEXT,  -- ← This must be TEXT not BOOLEAN
            locked BOOLEAN,
            is_original_content BOOLEAN,
            upvote_ratio FLOAT
        );
        """
    cur.execute(create_table_query)
    conn.commit()
    print(" Reddit table created or verified.")

    # Optional: print existing number of rows for debugging
    cur.execute(f"SELECT COUNT(*) FROM {db_table};")
    count = cur.fetchone()[0]
    print(f" Existing posts in DB: {count}")

    cur.close()
    conn.close()

# ---------------------- Reddit ----------------------
def connect_to_reddit() -> praw.Reddit:
    creds = get_secret(REDDIT_SECRET)
    print(" Connected to Reddit API.")
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        user_agent=creds["user_agent"],
    )

# ---------------------- Scraping + Insert ----------------------
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

    insert_query = f"""
        INSERT INTO {subreddit_name} (
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

    print(f" Scraping self-posts in r/{subreddit_name} since {cutoff_dt.date()}...")

    for submission in subreddit.new(limit=None):
        if submission.created_utc < cutoff_ts:
            break

        if submission.is_self:
            post = {
                "id": submission.id,
                "title": submission.title,
                "subreddit": str(submission.subreddit),
                "created_utc": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                "num_comments": submission.num_comments,
                "selftext": submission.selftext,
                "locked": submission.locked,
                "is_original_content": submission.is_original_content,
                "upvote_ratio": submission.upvote_ratio,
            }
            post_batch.append(post)
            total_collected += 1
            print(f" Collected {total_collected} self-posts...")

            if len(post_batch) == 10:
                for post in post_batch:
                    cur.execute(insert_query, (
                        post["id"],
                        post["title"],
                        post["subreddit"],
                        post["created_utc"],
                        post["num_comments"],
                        post["selftext"],
                        post["locked"],
                        post["is_original_content"],
                        post["upvote_ratio"],
                    ))
                conn.commit()
                print(" Inserted batch of 10 posts.")
                post_batch = []

        time.sleep(SLEEP_SECONDS)

    # Final insert if needed
    if post_batch:
        for post in post_batch:
            cur.execute(insert_query, (
                post["id"],
                post["title"],
                post["subreddit"],
                post["created_utc"],
                post["num_comments"],
                post["selftext"],
                post["locked"],
                post["is_original_content"],
                post["upvote_ratio"],
            ))
        conn.commit()
        print(f" Inserted final batch of {len(post_batch)} posts.")

    cur.close()
    conn.close()
    print(f"  {total_collected} posts.")

def print_reddit_table(db_table, limit=10):
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, title, subreddit, created_utc, num_comments, locked, is_original_content, upvote_ratio
        FROM {db_table} ORDER BY created_utc DESC LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()

    print(f"\n Showing {len(rows)} most recent posts from '{db_table}' table:")
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

    

# ---------------------- Main ----------------------
def main():
    for _ in range(len(DB_TABLE_NAMES)):
        setup_database(DB_TABLE_NAMES[_])
        reddit = connect_to_reddit()
        collect_and_insert_every_10(reddit, SUBREDDIT, CUTOFF_DATE)
        print_reddit_table(DB_TABLE_NAMES[_],limit=10)

if __name__ == "__main__":
    main()