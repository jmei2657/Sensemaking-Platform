import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

def scrape_kendrick_article(url):
    """
    Scrape the Kendrick Lamar article and extract relevant information
    """
    
    # Set headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Fetch the webpage
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract information about Kendrick Lamar
        kendrick_data = {
            'scrape_date': datetime.now().isoformat(),
            'source_url': url,
            'article_title': '',
            'achievements': [],
            'albums_mentioned': [],
            'awards': [],
            'cultural_impact': [],
            'academic_recognition': [],
            'quotes_about_kendrick': [],
            'collaborations': [],
            'influence_metrics': {}
        }
        
        # Get article title
        title_tag = soup.find('title')
        if title_tag:
            kendrick_data['article_title'] = title_tag.get_text().strip()
        
        # Get main article content
        article_content = ""
        
        # Try different common selectors for article content
        content_selectors = [
            'article',
            '.entry-content',
            '.post-content',
            '.article-content',
            'main',
            '.content'
        ]
        
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                article_content = content_element.get_text()
                break
        
        # If no specific content area found, get all text
        if not article_content:
            article_content = soup.get_text()
        
        # Extract specific information using regex and keyword matching
        text_lower = article_content.lower()
        
        # Extract achievements and awards
        achievement_patterns = [
            r'grammy awards?[^.]*?(\d+)[^.]*?awards?',
            r'won[^.]*?(\d+)[^.]*?grammy',
            r'pulitzer prize',
            r'super bowl[^.]*?halftime show',
            r'headliner?[^.]*?super bowl'
        ]
        
        for pattern in achievement_patterns:
            matches = re.findall(pattern, article_content, re.IGNORECASE)
            if matches:
                kendrick_data['achievements'].extend(matches)
        
        # Extract album mentions
        album_patterns = [
            r'(to pimp a butterfly)',
            r'(damn\.?)',
            r'(mr\.? morale & the big steppers)',
            r'(good kid m\.?a\.?a\.?d city)',
            r'(section\.80)'
        ]
        
        for pattern in album_patterns:
            matches = re.findall(pattern, article_content, re.IGNORECASE)
            if matches:
                kendrick_data['albums_mentioned'].extend([match.title() for match in matches])
        
        # Extract quotes about Kendrick
        quote_pattern = r'"([^"]*kendrick[^"]*)"'
        quotes = re.findall(quote_pattern, article_content, re.IGNORECASE)
        kendrick_data['quotes_about_kendrick'] = quotes
        
        # Extract cultural impact indicators
        impact_keywords = [
            'cultural impact', 'cultural moment', 'defined it', 'leading voice',
            'redefined boundaries', 'center of popular culture', 'legacy',
            'cultural significance', 'societal reverberations'
        ]
        
        for keyword in impact_keywords:
            if keyword in text_lower:
                # Find the sentence containing this keyword
                sentences = article_content.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        kendrick_data['cultural_impact'].append(sentence.strip())
                        break
        
        # Extract academic recognition
        academic_keywords = [
            'temple university', 'course', 'class', 'professor', 'academic',
            'university', 'study', 'scholar'
        ]
        
        for keyword in academic_keywords:
            if keyword in text_lower:
                sentences = article_content.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower() and 'kendrick' in sentence.lower():
                        kendrick_data['academic_recognition'].append(sentence.strip())
        
        # Extract numerical metrics if available
        metrics_patterns = {
            'grammy_wins': r'(\d+)\s*grammy',
            'year_mentioned': r'20\d{2}',
        }
        
        for metric, pattern in metrics_patterns.items():
            matches = re.findall(pattern, article_content, re.IGNORECASE)
            if matches:
                kendrick_data['influence_metrics'][metric] = matches
        
        # Clean up data - remove duplicates
        for key in kendrick_data:
            if isinstance(kendrick_data[key], list):
                kendrick_data[key] = list(set(kendrick_data[key]))
        
        return kendrick_data
        
    except requests.RequestException as e:
        return {'error': f'Failed to fetch webpage: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to parse content: {str(e)}'}

def display_results(data):
    """
    Display the scraped data in a readable format
    """
    if 'error' in data:
        print(f"Error: {data['error']}")
        return
    
    print("=" * 60)
    print("KENDRICK LAMAR - SCRAPED INFORMATION")
    print("=" * 60)
    print(f"Source: {data['source_url']}")
    print(f"Scraped: {data['scrape_date']}")
    print(f"Article: {data['article_title']}")
    print()
    
    if data['achievements']:
        print("ACHIEVEMENTS:")
        for achievement in data['achievements']:
            print(f"  • {achievement}")
        print()
    
    if data['albums_mentioned']:
        print("ALBUMS MENTIONED:")
        for album in data['albums_mentioned']:
            print(f"  • {album}")
        print()
    
    if data['quotes_about_kendrick']:
        print("QUOTES ABOUT KENDRICK:")
        for quote in data['quotes_about_kendrick']:
            print(f"  • \"{quote}\"")
        print()
    
    if data['cultural_impact']:
        print("CULTURAL IMPACT:")
        for impact in data['cultural_impact']:
            print(f"  • {impact}")
        print()
    
    if data['academic_recognition']:
        print("ACADEMIC RECOGNITION:")
        for recognition in data['academic_recognition']:
            print(f"  • {recognition}")
        print()
    
    if data['influence_metrics']:
        print("INFLUENCE METRICS:")
        for metric, values in data['influence_metrics'].items():
            print(f"  • {metric}: {values}")
        print()

def save_to_json(data, filename='kendrick_data.json'):
    """
    Save the scraped data to a JSON file
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Failed to save data: {str(e)}")

# Main execution
if __name__ == "__main__":
    url = "https://thesource.com/2025/06/24/temple-university-professor-to-teach-a-course-on-kendrick-lamar/"
    
    print("Scraping Kendrick Lamar article...")
    scraped_data = scrape_kendrick_article(url)
    
    # Display results
    display_results(scraped_data)
    
    # Save to JSON file
    if 'error' not in scraped_data:
        save_to_json(scraped_data)
    
    print("\nScraping complete!")
