"""
tweet_scrape_verified_since20240420_all.py
—
Scrape 400 verified tweets since 20 Apr 2024 for each of:
    #sza, #beyonce, #taylorswift, #blackpink, #straykids
Combine everything into ONE output file.
"""

import json
import logging
from pathlib import Path
from typing import List

import boto3
from botocore.exceptions import ClientError
from apify_client import ApifyClient

# ── Config ──────────────────────────────────────────────────────────
SECRET_NAME   = "apify_api_key"
AWS_REGION    = "us-east-1"
OUTPUT_FILE   = Path("verified_since20240420_all.json")

HASHTAGS      = ["sza", "beyonce", "taylorswift", "blackpink", "straykids"]
SINCE_DATE    = "2024-04-20"
ITEMS_PER_TAG = 400

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────
def get_secret() -> str:
    """Return the Apify API token stored in AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=AWS_REGION)
    try:
        data = json.loads(client.get_secret_value(SecretId=SECRET_NAME)["SecretString"])
        return data["APIFY_KEY"]
    except (ClientError, KeyError, json.JSONDecodeError) as e:
        log.error("Could not load APIFY_KEY from secret %s: %s", SECRET_NAME, e)
        raise


def _reduce(tweet: dict, tag: str) -> dict:
    """Trim tweet to essential fields and annotate with hashtag used."""
    author = tweet.get("author", {})
    return {
        "hashtag":      tag,
        "id":           tweet["id"],
        "createdAt":    tweet["createdAt"],
        "text":         tweet["text"],
        "retweetCount": tweet.get("retweetCount", 0),
        "replyCount":   tweet.get("replyCount", 0),
        "likeCount":    tweet.get("likeCount", 0),
        "quoteCount":   tweet.get("quoteCount", 0),
        "userName":     author.get("userName", ""),
    }


def scrape_tag(client: ApifyClient, tag: str) -> List[dict]:
    query = f"#{tag} filter:verified since:{SINCE_DATE}"
    run_input = {"searchTerms": [query], "maxItems": ITEMS_PER_TAG}

    log.info("▶  %s | scraping …", tag)
    run = client.actor("apidojo/tweet-scraper").call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]

    raw = list(client.dataset(dataset_id).iterate_items())
    log.info("◀  %s | got %d tweets", tag, len(raw))
    return [_reduce(t, tag) for t in raw]


# ── Main ────────────────────────────────────────────────────────────
def main() -> None:
    api_token = get_secret()
    client = ApifyClient(api_token)

    all_tweets: List[dict] = []
    for tag in HASHTAGS:
        all_tweets.extend(scrape_tag(client, tag))

    OUTPUT_FILE.write_text(json.dumps(all_tweets, indent=2, ensure_ascii=False))
    log.info("💾  combined %d tweets → %s", len(all_tweets), OUTPUT_FILE.resolve())


if __name__ == "__main__":
    try:
        main()
        log.info("Done ✔")
    except Exception:
        log.exception("Script failed")
        raise
