from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import json

# Set metadata
now = datetime.now()
uid = f"pagesix_taylor_{now.strftime('%Y%m%d_%H%M')}"
filename = f"{uid}.json"
log_file = "scrape_log.txt"

url = "https://pagesix.com/tag/taylor-swift/"

# Start browser and scrape HTML
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url)
    page.wait_for_timeout(7000)
    html = page.content()
    browser.close()

# Parse HTML
soup = BeautifulSoup(html, "html.parser")
headlines = soup.find_all("h3", class_="story__headline headline headline--archive")
print(f"🔎 Found {len(headlines)} articles")

articles = []

for h3 in headlines:
    title = h3.get_text(strip=True)

    # Extract article link
    link_tag = h3.find("a")
    link = link_tag["href"] if link_tag and link_tag.get("href") else "No link"

    # Extract timestamp (near the h3)
    timestamp_tag = h3.find_next("span", class_="meta meta--byline")
    raw_timestamp = timestamp_tag.get_text(strip=True) if timestamp_tag else "No timestamp"

    # Format timestamp (if it's in a standard format like "June 19, 2025 | 9:08am")
    try:
        dt = datetime.strptime(raw_timestamp, "%B %d, %Y | %I:%M%p")
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp = raw_timestamp  # Use raw if format is unexpected

    # Excerpt
    excerpt_tag = h3.find_next("p", class_="story__excerpt body")
    excerpt = excerpt_tag.get_text(strip=True) if excerpt_tag else "No excerpt"

    articles.append({
        "title": title,
        "link": link,
        "timestamp": timestamp,
        "excerpt": excerpt,
        "uid": uid
    })

# Save to JSON
with open(filename, "w", encoding="utf-8") as f:
    json.dump(articles, f, indent=2, ensure_ascii=False)

# Log the scrape
with open(log_file, "a", encoding="utf-8") as log:
    log.write(f"{now.strftime('%Y-%m-%d %H:%M:%S')} | UID: {uid} | Articles scraped: {len(articles)}\n")

print(f"✅ Scraped and saved {len(articles)} articles to {filename}")
print(f"📝 Log written to {log_file}")





