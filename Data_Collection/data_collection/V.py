from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import hashlib
import json
import os

url = "https://variety.com/t/taylor-swift/"
articles = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)  # Wait 5 seconds for JS to load content
    except Exception as e:
        print(f"❌ Failed to load page: {e}")
        browser.close()
        exit()

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    for h3 in soup.find_all("h3", class_="c-title"):
        a_tag = h3.find("a")
        if not a_tag or "taylor swift" not in a_tag.text.strip().lower():
            continue

        title = a_tag.text.strip()
        link = a_tag["href"].strip()

        # Traverse upward to find timestamp in parent containers
        time_tag = None
        parent = h3.find_parent()
        for _ in range(3):
            if parent and not time_tag:
                time_tag = parent.find("time")
                parent = parent.find_parent()

        timestamp = time_tag["datetime"] if time_tag and "datetime" in time_tag.attrs else "N/A"
        uid = hashlib.md5(link.encode()).hexdigest()

        articles.append({
            "title": title,
            "timestamp": timestamp,
            "uid": uid
        })

    browser.close()

# Save output
output_filename = "variety_articles.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=4)

print(f"✅ {len(articles)} articles saved to: {os.path.abspath(output_filename)}")





