import boto3
import json
import psycopg2
from botocore.exceptions import ClientError
from datetime import datetime
from dateutil.parser import parse as parse_date

# ---------- CONFIGURATION ----------
AWS_REGION = "us-east-1"
DB_SECRET_NAME = "DB"
JSON_FILE = "vulture_taylor_swift_DONE.json"
TABLE_NAME = "Vulturetaylor"
# -----------------------------------

# --------- Get Secrets from AWS Secrets Manager ---------
def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        print("Failed to get secret:", e)
        raise e

# --------- Connect to Postgres DB ----------
def connect_db():
    creds = get_secret(DB_SECRET_NAME)
    conn = psycopg2.connect(
        dbname=creds['dbname'],
        user=creds['user'],
        password=creds['password'],
        host=creds['host'],
        port=creds['port']
    )
    return conn

# --------- Create Table if not exists ----------
def setup_database():
    conn = connect_db()
    cur = conn.cursor()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        uid TEXT PRIMARY KEY,
        title TEXT,
        timestamp TIMESTAMPTZ,
        url TEXT,
        text TEXT
    );
    """

    cur.execute(create_table_sql)
    conn.commit()
    print(f"✅ Table '{TABLE_NAME}' created or already exists.")
    cur.close()
    conn.close()

# --------- Load JSON Articles ----------
def load_articles_from_json():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# --------- Insert articles into DB ----------
def insert_articles(articles):
    conn = connect_db()
    cur = conn.cursor()

    insert_sql = f"""
    INSERT INTO {TABLE_NAME} (uid, title, timestamp, url, text)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (uid) DO NOTHING;
    """

    inserted = 0
    for article in articles:
        try:
            uid = article.get("uid")
            title = article.get("title")
            timestamp_val = article.get("timestamp")
            url = article.get("url")
            text = article.get("text")  # changed from 'context' to 'text'

            timestamp = None
            if timestamp_val:
                try:
                    timestamp = parse_date(timestamp_val)
                except Exception:
                    pass

            cur.execute(insert_sql, (uid, title, timestamp, url, text))
            inserted += 1
        except Exception as e:
            print(f"⚠️ Skipping article due to error: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Inserted {inserted} articles into '{TABLE_NAME}'.")

# --------- Main ----------
def main():
    setup_database()
    articles = load_articles_from_json()
    insert_articles(articles)

if __name__ == "__main__":
    main()
