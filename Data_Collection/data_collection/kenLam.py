import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
import time

class BillboardScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_kendrick_page(self, url="https://www.billboard.com/artist/kendrick-lamar/"):
        """Scrape Kendrick Lamar's Billboard artist page"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract artist data
            artist_data = {
                'name': 'Kendrick Lamar',
                'url': url,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'biography': self.extract_biography(soup),
                'basic_info': self.extract_basic_info(soup),
                'achievements': self.extract_achievements(soup),
                'albums': self.extract_albums(soup),
                'chart_info': self.extract_chart_info(soup),
                'news_articles': self.extract_news(soup),
                'images': self.extract_images(soup, url)
            }
            
            return artist_data
            
        except requests.RequestException as e:
            print(f"Error fetching page: {e}")
            return None
    
    def extract_biography(self, soup):
        """Extract biography/description text"""
        bio_text = ""
        
        # Look for common biography selectors
        bio_selectors = [
            'p',
            '.artist-bio',
            '.biography',
            '.description',
            '[class*="bio"]',
            '[class*="description"]'
        ]
        
        for selector in bio_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if len(text) > 100 and any(keyword in text.lower() for keyword in ['kendrick', 'rapper', 'hip-hop', 'album']):
                    bio_text = text
                    break
            if bio_text:
                break
                
        return bio_text
    
    def extract_basic_info(self, soup):
        """Extract basic information like birthday, height, etc."""
        info = {}
        
        # Look for structured data or specific info
        text = soup.get_text()
        
        # Extract birthday
        birthday_match = re.search(r'birthday is ([^,]+)', text, re.IGNORECASE)
        if birthday_match:
            info['birthday'] = birthday_match.group(1).strip()
            
        # Extract height
        height_match = re.search(r'height is ([^.]+)', text, re.IGNORECASE)
        if height_match:
            info['height'] = height_match.group(1).strip()
            
        return info
    
    def extract_achievements(self, soup):
        """Extract awards and achievements"""
        achievements = []
        
        text = soup.get_text()
        
        # Look for Pulitzer Prize mention
        if 'pulitzer prize' in text.lower():
            achievements.append("First MC to win a Pulitzer Prize")
            
        # Look for Grammy mentions
        grammy_match = re.search(r'grammy[^.]*', text, re.IGNORECASE)
        if grammy_match:
            achievements.append(grammy_match.group(0))
            
        return achievements
    
    def extract_albums(self, soup):
        """Extract album information"""
        albums = []
        
        # Look for album mentions in text
        text = soup.get_text()
        
        # Common album patterns
        album_patterns = [
            r"'([^']+)'",  # Single quotes
            r'"([^"]+)"',  # Double quotes
        ]
        
        for pattern in album_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if any(keyword in match.lower() for keyword in ['album', 'city', 'butterfly', 'damn', 'steppers']):
                    if match not in albums and len(match) > 3:
                        albums.append(match)
        
        return albums
    
    def extract_chart_info(self, soup):
        """Extract chart performance data"""
        chart_info = {}
        
        # Look for Billboard chart mentions
        text = soup.get_text()
        
        if 'billboard 200' in text.lower():
            chart_info['billboard_200'] = "Has No. 1 albums on Billboard 200"
            
        if 'no. 1' in text.lower():
            chart_info['number_one_hits'] = "Has achieved No. 1 hits"
            
        return chart_info
    
    def extract_news(self, soup):
        """Extract recent news articles"""
        news = []
        
        # Look for news/article links
        news_selectors = [
            'article',
            '.news-item',
            '.article-item',
            'a[href*="news"]',
            'a[href*="article"]'
        ]
        
        for selector in news_selectors:
            elements = soup.select(selector)
            for elem in elements[:5]:  # Limit to first 5
                title = elem.get_text(strip=True)
                link = elem.get('href') if elem.name == 'a' else elem.find('a')
                
                if title and len(title) > 10:
                    news_item = {'title': title}
                    if link:
                        news_item['url'] = link if link.startswith('http') else urljoin("https://www.billboard.com", link)
                    news.append(news_item)
                    
        return news
    
    def extract_images(self, soup, base_url):
        """Extract image URLs"""
        images = []
        
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            alt = img.get('alt', '')
            
            if src and ('kendrick' in alt.lower() or 'lamar' in alt.lower() or len(alt) == 0):
                full_url = urljoin(base_url, src)
                images.append({
                    'url': full_url,
                    'alt_text': alt
                })
                
        return images[:10]  # Limit to first 10 images
    
    def save_to_file(self, data, filename='kendrick_lamar_data.json'):
        """Save scraped data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving file: {e}")
    
    def print_summary(self, data):
        """Print a summary of scraped data"""
        if not data:
            print("No data to display")
            return
            
        print("=" * 50)
        print(f"KENDRICK LAMAR - BILLBOARD DATA")
        print("=" * 50)
        print(f"Scraped at: {data['scraped_at']}")
        print(f"URL: {data['url']}")
        print()
        
        if data['biography']:
            print("BIOGRAPHY:")
            print(data['biography'][:300] + "..." if len(data['biography']) > 300 else data['biography'])
            print()
        
        if data['basic_info']:
            print("BASIC INFO:")
            for key, value in data['basic_info'].items():
                print(f"  {key.title()}: {value}")
            print()
        
        if data['achievements']:
            print("ACHIEVEMENTS:")
            for achievement in data['achievements']:
                print(f"  • {achievement}")
            print()
        
        if data['albums']:
            print("ALBUMS MENTIONED:")
            for album in data['albums']:
                print(f"  • {album}")
            print()
        
        if data['chart_info']:
            print("CHART PERFORMANCE:")
            for key, value in data['chart_info'].items():
                print(f"  • {value}")
            print()
        
        print(f"Found {len(data['news_articles'])} news items")
        print(f"Found {len(data['images'])} images")

def main():
    """Main function to run the scraper"""
    scraper = BillboardScraper()
    
    print("Scraping Kendrick Lamar's Billboard page...")
    data = scraper.scrape_kendrick_page()
    
    if data:
        scraper.print_summary(data)
        scraper.save_to_file(data)
        
        # Optional: Return data for further processing
        return data
    else:
        print("Failed to scrape data")
        return None

if __name__ == "__main__":
    scraped_data = main()
