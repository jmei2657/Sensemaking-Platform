import requests
from bs4 import BeautifulSoup
import json

def scrape_bi_article(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ScraperBot/1.0)"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract article title
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else 'No title found'

    # Extract article body content
    article_body = soup.find('section', attrs={'role': 'main'})
    if not article_body:
        article_body = soup  # fallback to entire page

    paragraphs = article_body.find_all('p')
    content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

    return {
        'title': title,
        'url': url,
        'content': content
    }

if __name__ == "__main__":
    url = "https://www.businessinsider.com/kendrick-lamar-sza-tour-drake-diss-tracks-review-2025-5?utm_source=chatgpt.com"
    article = scrape_bi_article(url)

    # Save to JSON file
    with open("kendrick_sza_bi_article.json", "w", encoding="utf-8") as f:
        json.dump(article, f, indent=2, ensure_ascii=False)

    print("Article saved to 'kendrick_sza_bi_article.json'")