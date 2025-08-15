import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from playwright.sync_api import sync_playwright

START_URL = "https://www.complex.com/tag/sza"
DOMAIN = "https://www.complex.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

visited = set()
to_visit = [START_URL]
articles = []

# Cutoff date: April 18, 2024 UTC
CUTOFF_DATE = datetime(2024, 4, 18, tzinfo=timezone.utc)

# Helper to parse relative dates like "12 days ago"
def parse_relative_date(relative_text):
    try:
        if "day" in relative_text:
            num = int(re.search(r"(\d+)", relative_text).group(1))
            return datetime.now(timezone.utc) - timedelta(days=num)
        elif "hour" in relative_text:
            num = int(re.search(r"(\d+)", relative_text).group(1))
            return datetime.now(timezone.utc) - timedelta(hours=num)
        elif "minute" in relative_text:
            num = int(re.search(r"(\d+)", relative_text).group(1))
            return datetime.now(timezone.utc) - timedelta(minutes=num)
    except:
        return None
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    while to_visit:
        current_url = to_visit.pop(0)
        if current_url in visited:
            continue

        print(f"Visiting: {current_url}")
        visited.add(current_url)

        try:
            page.goto(current_url, timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"Error loading {current_url}: {e}")
            continue

        soup = BeautifulSoup(page.content(), "html.parser")

        # Find article blocks
        for a_tag in soup.find_all("a", class_="megaFeedCardDetails", href=True):
            link = urljoin(DOMAIN, a_tag['href'])
            if link in visited:
                continue

            title_tag = a_tag.find("p", class_="megaFeedCardHeadline")
            date_tag = a_tag.find("p", class_="megaFeedCardPublishedAt")

            title = title_tag.get_text(strip=True) if title_tag else "No Title"
            relative_date_text = date_tag.get_text(strip=True) if date_tag else ""
            dt = parse_relative_date(relative_date_text)

            if not dt or dt <= CUTOFF_DATE:
                print(f"  Skipping article '{title}' (date: {relative_date_text})")
                continue

            # Visit individual article page to get full text
            print(f"  Scraping article: {title}")
            try:
                page.goto(link, timeout=30000)
                time.sleep(1)
                article_soup = BeautifulSoup(page.content(), "html.parser")

                # Main article text container (common structure)
                article_div = article_soup.find("div", class_=lambda c: c and "articleBody" in c)
                if not article_div:
                    paragraphs = article_soup.find_all("p")
                else:
                    paragraphs = article_div.find_all("p")

                text = "\n\n".join([p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True)])

                uid = hashlib.md5(link.encode()).hexdigest()

                articles.append({
                    "title": title,
                    "timestamp": dt.isoformat(),
                    "uid": uid,
                    "url": link,
                    "text": text
                })
                visited.add(link)

            except Exception as e:
                print(f"  Error scraping {link}: {e}")

    browser.close()

# Save to JSON
output_file = "nme_sza_articles_complex.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"\n✅ Crawl complete. {len(articles)} articles saved to {output_file}")