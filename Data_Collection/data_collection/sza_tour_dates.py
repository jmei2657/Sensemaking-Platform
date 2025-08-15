import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json

def scrape_tours(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ScraperBot/1.0)"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    tours = []
    dates = soup.select('div.date[data-date]')

    # Get list of ISO date strings
    data_date_list = [d['data-date'] for d in dates]

    blocks = soup.select('.cover-block')
    for i, block in enumerate(blocks):
        # Link (as title placeholder)
        link_tag = block.select_one('.cover-link')
        title = link_tag['href'] if link_tag else 'No title'

        # ISO date to formatted string
        raw_date = data_date_list[i] if i < len(data_date_list) else None
        try:
            full_date = datetime.fromisoformat(raw_date).strftime('%b %d, %Y')
        except:
            full_date = None

        # Location
        loc_tag = block.select_one('.date-name')
        location = loc_tag.get_text(strip=True) if loc_tag else 'No location'

        tours.append({
            'title': title,
            'date': full_date,
            'location': location
        })

    return tours

if __name__ == "__main__":
    url = "https://szatour.info/"
    tours = scrape_tours(url)

    # Save to JSON file
    with open("sza_tour_dates.json", "w", encoding="utf-8") as f:
        json.dump(tours, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(tours)} tour dates to 'sza_tour_dates.json'")