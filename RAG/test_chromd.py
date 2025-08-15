import json
import psycopg2
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import boto3
from botocore.exceptions import ClientError
import re
from typing import List, Dict, Tuple, Optional
import logging
import os
from langchain_community.llms import Ollama
import datetime
from dateutil import parser as date_parser
from chunking_config import (
    get_chunking_params, 
    get_preprocessing_config, 
    get_metadata_config, 
    get_search_config
)

# ── Load secrets from AWS ──────────────────────────────────────
AWS_REGION = "us-east-1"


def get_secret(secret_name: str, region_name: str = AWS_REGION) -> dict:
    session = boto3.session.Session()
    client = session.client("secretsmanager", region_name=region_name)
    try:
        secret = client.get_secret_value(SecretId=secret_name)["SecretString"]
        return json.loads(secret)
    except ClientError as e:
        raise RuntimeError(f"Error getting secret {secret_name}: {e}")

# ── Connect to Postgres ────────────────────────────────────────


def connect_db():
    creds = get_secret("DB")
    return psycopg2.connect(
        dbname=creds["dbname"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=creds["port"]
    )


# ── Fetch from `reddit` ─────────────────────────────────────────
def fetch_reddit_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, selftext, created_utc FROM reddit;")
        return cur.fetchall()

# ── Fetch from `newsapi` ───────────────────────────────────────────


def fetch_newsapi_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uid::text, title, description, timestamp FROM newsapi;")
        return cur.fetchall()

# ── Fetch from `tmz` ───────────────────────────────────────────


def fetch_tmz_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, excerpt, published_date FROM tmz;")
        return cur.fetchall()

# ── Fetch from `guardian` ──────────────────────────────────────


def fetch_guardian_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title_context, date_timestamp FROM guardian;")
        return cur.fetchall()

# ── Fetch from `sza_tours` ──────────────────────────────────────


def fetch_sza_tours_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, artist, title, location, date FROM dc_sza_tours;")
        return cur.fetchall()

# ── Fetch from `szanme`──────────────────────────────────────


def fetch_szanme_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, timestamp FROM szanme;")
        return cur.fetchall()

# ── Fetch from `taylornme` ──────────────────────────────────────


def fetch_taylornme_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, timestamp FROM taylornme;")
        return cur.fetchall()

# ── Fetch from `reddit_billie` ─────────────────────────────────────────


def fetch_reddit_billie_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM reddit_billie;")
        return cur.fetchall()

# ── Fetch from `reddit_blackpink` ─────────────────────────────────────────


def fetch_reddit_blackpink_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM reddit_blackpink;")
        return cur.fetchall()

# ── Fetch from `reddit_straykids` ─────────────────────────────────────────


def fetch_reddit_straykids_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM reddit_straykids;")
        return cur.fetchall()

# ── Fetch from `reddit_sza` ─────────────────────────────────────────


def fetch_reddit_sza_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, selftext, created_utc FROM reddit_sza;")
        return cur.fetchall()

# ── Fetch from `tmz_billie` ─────────────────────────────────────────


def fetch_tmz_billie_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT uid, title, excerpt, published_date FROM tmz_billie;")
        return cur.fetchall()

# ── Fetch from `tmz_sza` ─────────────────────────────────────────


def fetch_tmz_sza_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, excerpt, published_date FROM tmz_sza;")
        return cur.fetchall()


def fetch_vulturetaylor_articles():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, text, timestamp FROM vulturetaylor;")
        return cur.fetchall()


def fetch_reddit_popculture_taylor_posts():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM popculture_reddit_taylor;")
        return cur.fetchall()


def fetch_kpop_reddit_blackpink():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM kpop_reddit_blackpink;")
        return cur.fetchall()


def fetch_kpop_reddit_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM kpop_reddit_straykids;")
        return cur.fetchall()


def fetch_popculture_reddit_billie():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM popculture_reddit_billie;")
        return cur.fetchall()


def fetch_popculture_reddit_blackpink():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM popculture_reddit_blackpink;")
        return cur.fetchall()


def fetch_popculture_reddit_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM popculture_reddit_straykids;")
        return cur.fetchall()


def fetch_popculture_reddit_sza():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, selftext, created_utc FROM popculture_reddit_sza;")
        return cur.fetchall()


def fetch_billboard():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uuid, title, rank, weekdate, artist FROM billboard;")
        return cur.fetchall()


def fetch_blackpink_tours():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid,  venue, region, tour_date FROM blackpink_tours;")
        return cur.fetchall()
    

    

def fetch_beyonce_tmz():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, published_date FROM beyonce_tmz;")
        return cur.fetchall()

def fetch_twitter():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT tweet_id, username, content, created_at FROM tweets;")
        return cur.fetchall()

def fetch_guardian_beyonce():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title_context, date_timestamp FROM guardian_beyonce;")
        return cur.fetchall()

def fetch_news_beyonce():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, description, timestamp FROM news_beyonce;")
        return cur.fetchall()

def fetch_popculture_reddit_beyonce():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, selftext, created_utc FROM popculture_reddit_beyonce;")
        return cur.fetchall()

def fetch__reddit_beyonce():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, selftext, created_utc FROM reddit_beyonce;")
        return cur.fetchall()


def fetch_kpopnoir_reddit_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, selftext, created_utc FROM kpopnoir_reddit_straykids;")
        return cur.fetchall()

def fetch_newsapi_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, title, description, timestamp FROM newsapi_straykids;")
        return cur.fetchall()

def fetch_ticketmaster_beyonce_events():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, name, city, event_date FROM ticketmaster_beyonce_events;")
        return cur.fetchall()

def fetch_straykids_tours():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, location, artist, tour_date FROM straykids_tours;")
        return cur.fetchall()
    
def fetch_dc_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, content, published_date FROM dc_straykids2;")
        return cur.fetchall()



def fetch_nbc_straykids():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, content, published_date FROM nbc_straykids;")
        return cur.fetchall()


def fetch_change_petitions():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, description, created_date FROM change_petitions;")
        return cur.fetchall()

def fetch_apify_youtube_events():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT uid, artist, title, date FROM apify_youtube_events;")
        return cur.fetchall()

def fetch_dc_straykids2():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, content, published_date FROM dc_straykids3;")
        return cur.fetchall()





# ── Setup ChromaDB ─────────────────────────────────────────────
def setup_chroma():
    return chromadb.PersistentClient(path="./chroma_storage")

# ── Text Preprocessing ──────────────────────────────────────────


def preprocess_text(text: str) -> str:
    """Clean and normalize text for chunking."""
    if not text:
        return ""

    config = get_preprocessing_config()

    if config["normalize_whitespace"]:
        text = re.sub(r'\s+', ' ', text.strip())

    if config["remove_special_chars"]:
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]]', '', text)

    if config["remove_urls"]:
        text = re.sub(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

    if config["remove_emails"]:
        text = re.sub(r'\S+@\S+', '', text)

    if config["lowercase"]:
        text = text.lower()

    if config["remove_numbers"]:
        text = re.sub(r'\d+', '', text)

    # Check minimum length
    if len(text.strip()) < config["min_text_length"]:
        return ""

    return text.strip()

# ── Simple Chunking ────────────────────────────────────────────


def simple_chunk(text: str, chunk_size: int = 512, overlap: int = 50) -> list:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def get_dynamic_chunk_params(text_length):

    if text_length < 500:
        return 256, 32
    elif text_length < 2000:
        return 512, 50
    else:
        return 768, 75


def embed_data_with_chunking(rows, collection_name, embedder, client, chunk_size=512, overlap=50):
    collection = client.get_or_create_collection(name=collection_name)
    ids, texts, metadatas = [], [], []
    id_set = set()
    chunk_type = collection_name.replace('_embeddings', '')
    for row in rows:
        date = None
        body = None
        location = None
        rank = None
        artist = None
        print(f"Processing row: {row}")

        # Process Billboard
        if len(row) == 5:
            uid, title, rank, date, artist = row
            # Filler text so that it actually gets embedded and used by the RAG this time!!!!!!!!!!!!!!!!!!!!!!!!!!!
            body = f"""
                    The song "{title}" by {artist} reached position #{rank} on the Billboard Hot 100 for the week of {date}. 
                    It continues to resonate with listeners across streaming platforms and radio airwaves, capturing attention with its distinctive sound and emotional appeal. 
                    This week's performance highlights the artist's ongoing influence in today's music landscape.
                    """.strip()


        # Process other stuff
        elif len(row) == 4:
            uid, title, body, date = row
        elif len(row) == 3:
            uid, title, third = row
            if isinstance(third, (datetime.datetime, datetime.date)) or (
                isinstance(third, str) and (
                    third.count('-') >= 2 or third.count(',') == 1
                )
            ):
                body = None
                date = third
            else:
                body = third
        elif len(row) == 2:
            uid, title = row
            body = title
        else:
            continue
        # --- Beyonce tours date fix ---
        if collection_name == "beyonce_tours_embeddings" and date is not None and isinstance(date, str):
            import re
            # Match M.DD or MM.DD
            match = re.match(r"^(\d{1,2})[.](\d{1,2})$", date.strip())
            if match:
                month, day = match.groups()
                print(f"[DEBUG] Matched month: {month}, day: {day}")
                
                month = month.zfill(2)
                day = day.zfill(2)
                date = f"2025-{month}-{day}"
                print(f"[DEBUG] Transformed Beyonce tour date to: '{date}' (YYYY-MM-DD)")
            else:
                print(f"[DEBUG] Beyonce tour date did not match expected format: '{date}'")
        # Try to extract a date from title, body, or location if date is missing
        if date is None:
            for text_field in [title, body]:
                if text_field:
                    import re
                    date_match = re.search(
                        r'(\w{3,9} \d{1,2}, \d{4})', str(text_field))
                    if date_match:
                        try:
                            date = date_parser.parse(date_match.group(1))
                            print(f"Extracted date from text field: {date}")
                            break
                        except Exception as e:
                            print(f"Could not parse date from text field: {e}")
        # Always build a non-empty text for chunking
        full_text = f"{title or ''} {body or ''}".strip()
        if not full_text:
            full_text = title or ''  # fallback to title only
        full_text = preprocess_text(full_text)
        if not full_text:
            continue
        dynamic_chunk_size, dynamic_overlap = get_dynamic_chunk_params(
            len(full_text))
        chunks = simple_chunk(full_text, dynamic_chunk_size, dynamic_overlap)
        # --- Print and normalize date ---
        parsed_date = None
        date_str = None
        if date is not None:
            try:
                print(f"[DEBUG] Attempting to parse date: '{date}' (type: {type(date)})")
                if isinstance(date, (datetime.datetime, datetime.date)):
                    parsed_date = date
                    date_str = date.isoformat()
                else:
                    parsed_date = date_parser.parse(str(date))
                    date_str = parsed_date.isoformat()
                print(f"[DEBUG] Successfully parsed date: {parsed_date} (ISO: {date_str})")
            except Exception as e:
                print(f"Could not parse date '{date}': {e}")
                parsed_date = None
            print(
                f"Entry UID: {uid} | Raw date: {date} | Parsed datetime: {parsed_date}")
        else:
            print(f"Entry UID: {uid} | No date field present. Full row: {row}")
        for i, chunk in enumerate(chunks):
            base_id = f"{uid}_chunk_{i}"
            unique_id = base_id
            suffix = 1
            while unique_id in id_set:
                unique_id = f"{base_id}_{suffix}"
                suffix += 1
            id_set.add(unique_id)
            meta = {
                "title": title or "Untitled",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "original_id": uid,
                "chunk_strategy": "dynamic",
                "chunk_type": chunk_type
            }
            if collection_name == "billboard_embeddings":
                meta = {
                "title": title or "Untitled",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "original_id": uid,
                "chunk_strategy": "dynamic",
                "chunk_type": chunk_type,
                "rank": rank,
                "artist": artist,
                "date": date
                }
            if date_str is not None:
                meta["date"] = date_str
            print(f"DEBUG META: {meta}")
            metadatas.append(meta)
            ids.append(unique_id)
            texts.append(chunk)
    if not texts:
        logging.getLogger(__name__).info(
            f"No valid texts to embed in collection '{collection_name}'.")
        return
    logging.getLogger(__name__).info(
        f"Embedding {len(texts)} chunks into '{collection_name}'...")
    collection.add(documents=texts, ids=ids, metadatas=metadatas)
    logging.getLogger(__name__).info(
        f"Indexed {len(texts)} chunks into '{collection_name}'.")

# ── Run Semantic Search ─────────────────────────────────────────


def semantic_search(collection, query, top_k=5):
    print(f"\n Top {top_k} results for: '{query}'")
    results = collection.query(query_texts=[query], n_results=top_k)
    print("\nFull metadatas returned:")
    print(results["metadatas"][0])
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        print(f"\n[{i+1}] Metadata: {meta}")
        print(f"Document: {doc[:300]}{'...' if len(doc) > 300 else ''}")
        date_str = meta.get('date', None)
        parsed_date = None
        if date_str:
            try:
                parsed_date = date_parser.parse(date_str)
                print(f"Parsed datetime: {parsed_date}")
            except Exception as e:
                print(f"Could not parse date '{date_str}': {e}")
        else:
            # Try to parse a date from the document text itself
            date_match = re.search(r'(\w{3,9} \d{1,2}, \d{4})', doc)
            if date_match:
                try:
                    parsed_date = date_parser.parse(date_match.group(1))
                    # <-- Add to metadata for display
                    meta['date'] = parsed_date.isoformat()
                    print(f"Parsed date from document: {parsed_date}")
                except Exception as e:
                    print(f"Could not parse date from document: {e}")
            else:
                print("No date available for this entry.")
        # Now print the enriched metadata
        print(f"Enriched Metadata: {meta}")

# ── Clear and Rebuild Collections ──────────────────────────────


def clear_collections(client):
    """Clear existing collections to rebuild with new chunking strategy."""
    try:
        # Delete existing collections
        client.delete_collection("news_embeddings")
        print(" Deleted existing news_embeddings collection")
    except:
        print(" news_embeddings collection not found or already deleted")

    try:
        client.delete_collection("reddit_embeddings")
        print(" Deleted existing reddit_embeddings collection")
    except:
        print(" reddit_embeddings collection not found or already deleted")

    # try:
    #     client.delete_collection("billboard_embeddings")
    #     print(" Deleted existing billboard_embeddings collection")
    # except:
    #     print(" billboard_embeddings collection not found or already deleted")

    print(" Collections cleared. Ready to rebuild with new chunking strategy.")

# ── Logging Setup ─────────────────────────────────────────────


def setup_logging(log_file='vector_log.log'):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    logger = logging.getLogger(__name__)
    logger.info("Logging is set up and working.")
    return logger

# ── LLM Loader with Temperature ───────────────────────────────


def load_llm(temperature):
    os.system("ollama pull llama3")
    llm = Ollama(model="llama3", temperature=temperature)
    logging.getLogger(__name__).info(
        f"Loaded LLM with temperature={temperature}")
    return llm

# ── Main Script ─────────────────────────────────────────────────


def main():
    logger = setup_logging()
    logger.info("Starting embedding process...")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    chroma_client = setup_chroma()
    load_llm(temperature=0.5)
    rebuild_collections = True
    if rebuild_collections:
        logger.info("Rebuilding collections with new chunking strategy...")
        clear_collections(chroma_client)
        # Embed all sources using the unified chunking method
        for fetch_func, collection in [

            (fetch_dc_straykids, "dc_straykids_embeddings"),
            (fetch_reddit_posts, "reddit_embeddings"),
            (fetch_dc_straykids2, "dc_straykids_embeddings2"),
            (fetch_nbc_straykids, "nbc_straykids_embeddings"),
            (fetch_apify_youtube_events, "apify_youtube_events_embeddings"),
            (fetch_change_petitions, "change_petitions_embeddings"),

            (fetch_blackpink_tours, "blackpink_tours_embeddings"),
            (fetch_beyonce_tmz, "beyonce_tmz_embeddings"),
            (fetch_twitter, "twitter_embeddings"),
            (fetch_guardian_beyonce, "guardian_beyonce_embeddings"),
            (fetch_news_beyonce, "news_beyonce_embeddings"),
            (fetch_popculture_reddit_beyonce, "popculture_reddit_beyonce_embeddings"),
            (fetch__reddit_beyonce, "reddit_beyonce_embeddings"),
            (fetch_newsapi_articles, "newsapi_embeddings"),
            (fetch_reddit_posts, "reddit_embeddings"),
            (fetch_reddit_billie_posts, "reddit_billie_embeddings"),
            (fetch_reddit_blackpink_posts, "reddit_blackpink_embeddings"),
            (fetch_reddit_straykids_posts, "reddit_straykids_embeddings"),
            (fetch_reddit_sza_posts, "reddit_sza_embeddings"),
            (fetch_tmz_articles, "tmz_embeddings"),
            (fetch_tmz_billie_articles, "tmz_billie_embeddings"),
            (fetch_tmz_sza_articles, "tmz_sza_embeddings"),
            (fetch_sza_tours_articles, "sza_tours_embeddings"),
            (fetch_szanme_articles, "szanme_embeddings"),
            (fetch_taylornme_articles, "taylornme_embeddings"),
            (fetch_vulturetaylor_articles, "vulturetaylor_embeddings"),
            (fetch_reddit_popculture_taylor_posts,"popculture_reddit_taylor_embeddings"),
            (fetch_kpop_reddit_blackpink, "kpop_reddit_blackpink_embeddings"),
            (fetch_kpop_reddit_straykids, "kpop_reddit_straykids_embeddings"),
            (fetch_popculture_reddit_billie, "popculture_reddit_billie_embeddings"),
            (fetch_popculture_reddit_blackpink,
             "popculture_reddit_blackpink_embeddings"),
            (fetch_popculture_reddit_straykids,
             "popculture_reddit_straykids_embeddings"),
            (fetch_popculture_reddit_sza, "popculture_reddit_sza_embeddings"),
            (fetch_billboard, "billboard_embeddings"),

            (fetch_kpopnoir_reddit_straykids, "kpopnoir_reddit_straykids_embeddings"),
            (fetch_newsapi_straykids, "newsapi_straykids_embeddings"),
            (fetch_ticketmaster_beyonce_events, "ticketmaster_beyonce_events_embeddings"),
            (fetch_straykids_tours, "straykids_tours_embeddings")
        ]:
            print(f"Embedding for collection: {collection}")
            rows = fetch_func()
            embed_data_with_chunking(rows, collection, embedder, chroma_client)
    else:
        logger.info("Using existing collections (may have old metadata format)")
    # Query and print results for confirmation
    for collection_name, query in [
        ("billboard_embeddings", "Billboard Charts"),
        ("newsapi_embeddings", "Taylor Swift political news"),
        ("reddit_embeddings", "Taylor Swift fan theories"),
        ("reddit_billie_embeddings", "Billie Eilish fan theories"),
        ("reddit_blackpink_embeddings", "Blackpink fan theories"),
        ("reddit_straykids_embeddings", "Stray Kids fan theories"),
        ("reddit_sza_embeddings", "SZA fan theories"),
        ("tmz_embeddings", "Taylor Swift in TMZ"),
        ("tmz_billie_embeddings", "Billie Eilish in TMZ"),
        ("tmz_sza_embeddings", "SZA in TMZ"),
        ("sza_tours_embeddings", "SZA tours"),

        ("vulturetaylor_embeddings", "Taylor Swift in Vulture"),
        ("popculture_reddit_taylor_embeddings",
         "Taylor Swift in Reddit Popculture"),
        ("kpop_reddit_blackpink_embeddings", "Blackpink in Reddit Kpop"),
        ("kpop_reddit_straykids_embeddings", "Stray Kids in Reddit Kpop"),
        ("popculture_reddit_billie_embeddings",
         "Billie Eilish in Reddit Popculture"),
        ("popculture_reddit_blackpink_embeddings",
         "Blackpink in Reddit Popculture"),
        ("popculture_reddit_straykids_embeddings",
         "Stray Kids in Reddit Popculture"),
        ("popculture_reddit_sza_embeddings", "SZA in Reddit Popculture")

    ]:
        collection = chroma_client.get_collection(collection_name)
        semantic_search(collection, query)


if __name__ == "__main__":
    main()