import json

filename = "nme_taylor_swift_articles_playwright.json"

try:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print("❌ No articles found in the file.")
    else:
        print(f"\n✅ Loaded {len(data)} articles from {filename}\n")

        for i, article in enumerate(data, 1):
            print(f"--- Article {i} ---")
            print(f"Title    : {article.get('title', 'N/A')}")
            print(f"Date     : {article.get('timestamp', 'N/A')}")
            print(f"URL      : {article.get('url', 'N/A')}")
            print(f"Text     :\n{article.get('text', '')}\n")
            print("=" * 80 + "\n")

except FileNotFoundError:
    print(f"❌ File not found: {filename}")
except json.JSONDecodeError as e:
    print(f"❌ Failed to decode JSON: {e}")

