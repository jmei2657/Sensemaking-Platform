import boto3
import json
import praw
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# ---------- CONFIGURATION ----------
AWS_REGION     = "us-east-1"
REDDIT_SECRET  = "reddit_api_credentials"
SUBREDDIT      = "sza"
SEARCH_QUERY   = "sos tour"
CUTOFF_DATE    = datetime(2024, 4, 18, tzinfo=timezone.utc)
SLEEP_SECONDS  = 2
POST_LIMIT     = 1000
# -----------------------------------

# ---------------------- AWS Secrets ----------------------
def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print("❌ Failed to get secret:", e)
        raise e

# ---------------------- Reddit ----------------------
def connect_to_reddit() -> praw.Reddit:
    creds = get_secret(REDDIT_SECRET)
    print("✅ Connected to Reddit API.")
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        user_agent=creds["user_agent"],
    )

def collect_and_print_posts(reddit: praw.Reddit, subreddit_name: str, cutoff_dt: datetime):
    cutoff_ts = cutoff_dt.timestamp()
    subreddit = reddit.subreddit(subreddit_name)

    print(f"\n🔍 Searching r/{subreddit_name} for posts about '{SEARCH_QUERY}' since {cutoff_dt.date()}...\n")
    count = 0

    for submission in subreddit.search(SEARCH_QUERY, sort="new", time_filter="year", limit=POST_LIMIT):
        if submission.created_utc < cutoff_ts:
            continue

        created_str = datetime.utcfromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        print(f"""
🔹 Title: {submission.title}
🔗 URL: https://www.reddit.com{submission.permalink}
🕒 Date: {created_str}
💬 Comments: {submission.num_comments}
👍 Upvote Ratio: {submission.upvote_ratio}
📄 Selftext Preview: {submission.selftext[:200].strip() + '...' if submission.selftext else '[No selftext]'}
{'=' * 80}
""")
        count += 1
        time.sleep(SLEEP_SECONDS)

    print(f"\n📊 Total relevant posts found: {count}\n")

# ---------------------- Main ----------------------
def main():
    reddit = connect_to_reddit()
    collect_and_print_posts(reddit, SUBREDDIT, CUTOFF_DATE)

if __name__ == "__main__":
    main()