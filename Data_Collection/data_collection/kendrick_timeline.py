import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import time

def scrape_pglang_site(base_url):
    """
    Scrape the pgLang website and extract available information
    """
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    pglang_data = {
        'scrape_date': datetime.now().isoformat(),
        'base_url': base_url,
        'site_title': '',
        'dates_found': [],
        'clickable_links': [],
        'media_files': [],
        'meta_info': {},
        'site_structure': {},
        'potential_projects': []
    }
    
    try:
        # Fetch main page
        response = requests.get(base_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get site title
        title_tag = soup.find('title')
        if title_tag:
            pglang_data['site_title'] = title_tag.get_text().strip()
        
        # Extract meta information
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('name'):
                pglang_data['meta_info'][meta.get('name')] = meta.get('content', '')
            elif meta.get('property'):
                pglang_data['meta_info'][meta.get('property')] = meta.get('content', '')
        
        # Get all text content
        page_text = soup.get_text()
        
        # Extract dates (appears to be the main content)
        date_pattern = r'\b\d{2}-\d{2}-\d{2}\b'
        dates = re.findall(date_pattern, page_text)
        pglang_data['dates_found'] = sorted(list(set(dates)), reverse=True)
        
        # Look for any clickable links
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href')
            text = link.get_text().strip()
            if href and href != '#':
                pglang_data['clickable_links'].append({
                    'url': href,
                    'text': text,
                    'is_external': href.startswith('http') and base_url not in href
                })
        
        # Look for media files (images, videos)
        media_elements = soup.find_all(['img', 'video', 'audio'])
        for media in media_elements:
            src = media.get('src') or media.get('data-src')
            if src:
                pglang_data['media_files'].append({
                    'type': media.name,
                    'src': src,
                    'alt': media.get('alt', ''),
                    'title': media.get('title', '')
                })
        
        # Analyze site structure
        pglang_data['site_structure'] = {
            'has_navigation': bool(soup.find('nav')),
            'has_header': bool(soup.find('header')),
            'has_footer': bool(soup.find('footer')),
            'total_links': len(links),
            'total_images': len(soup.find_all('img')),
            'scripts_count': len(soup.find_all('script')),
            'stylesheets_count': len(soup.find_all('link', rel='stylesheet'))
        }
        
        # Try to access individual date pages (they might be clickable)
        sample_dates = pglang_data['dates_found'][:5]  # Test first 5 dates
        
        for date_str in sample_dates:
            try:
                # Try common URL patterns for date-based content
                potential_urls = [
                    f"{base_url}/{date_str}",
                    f"{base_url}#{date_str}",
                    f"{base_url}?date={date_str}"
                ]
                
                for test_url in potential_urls:
                    try:
                        test_response = requests.get(test_url, headers=headers, timeout=5)
                        if test_response.status_code == 200 and len(test_response.content) > len(response.content):
                            # Found additional content
                            test_soup = BeautifulSoup(test_response.content, 'html.parser')
                            project_info = {
                                'date': date_str,
                                'url': test_url,
                                'title': test_soup.find('title').get_text() if test_soup.find('title') else '',
                                'content_preview': test_soup.get_text()[:200] + '...' if len(test_soup.get_text()) > 200 else test_soup.get_text()
                            }
                            pglang_data['potential_projects'].append(project_info)
                            break
                    except:
                        continue
                        
                time.sleep(0.5)  # Be respectful with requests
                
            except Exception as e:
                continue
        
        # Check for JavaScript-rendered content
        scripts = soup.find_all('script')
        js_content = ""
        for script in scripts:
            if script.string:
                js_content += script.string
        
        if js_content:
            # Look for potential data or API endpoints in JavaScript
            api_pattern = r'["\']([^"\']*api[^"\']*)["\']'
            data_pattern = r'["\']([^"\']*data[^"\']*)["\']'
            
            api_matches = re.findall(api_pattern, js_content, re.IGNORECASE)
            data_matches = re.findall(data_pattern, js_content, re.IGNORECASE)
            
            if api_matches or data_matches:
                pglang_data['site_structure']['potential_api_endpoints'] = api_matches
                pglang_data['site_structure']['data_references'] = data_matches
        
        return pglang_data
        
    except requests.RequestException as e:
        return {'error': f'Failed to fetch webpage: {str(e)}'}
    except Exception as e:
        return {'error': f'Failed to parse content: {str(e)}'}

def analyze_pglang_data(data):
    """
    Analyze the scraped pgLang data for insights about the company/projects
    """
    if 'error' in data:
        return data
    
    analysis = {
        'timeline_analysis': {},
        'activity_patterns': {},
        'site_characteristics': {}
    }
    
    # Analyze dates for patterns
    if data['dates_found']:
        dates = data['dates_found']
        
        # Convert to datetime objects for analysis
        try:
            parsed_dates = []
            for date_str in dates:
                # Assuming YY-MM-DD format
                year = int('20' + date_str[:2])
                month = int(date_str[3:5])
                day = int(date_str[6:8])
                parsed_dates.append(datetime(year, month, day))
            
            analysis['timeline_analysis'] = {
                'earliest_date': min(parsed_dates).strftime('%Y-%m-%d'),
                'latest_date': max(parsed_dates).strftime('%Y-%m-%d'),
                'total_entries': len(dates),
                'years_active': len(set(d.year for d in parsed_dates)),
                'most_active_year': max(set(d.year for d in parsed_dates), key=lambda x: sum(1 for d in parsed_dates if d.year == x))
            }
            
            # Monthly activity
            monthly_activity = {}
            for date in parsed_dates:
                month_key = date.strftime('%Y-%m')
                monthly_activity[month_key] = monthly_activity.get(month_key, 0) + 1
            
            analysis['activity_patterns'] = {
                'most_active_month': max(monthly_activity.items(), key=lambda x: x[1]) if monthly_activity else None,
                'monthly_breakdown': monthly_activity
            }
            
        except Exception as e:
            analysis['timeline_analysis']['error'] = f'Could not parse dates: {str(e)}'
    
    # Site characteristics
    analysis['site_characteristics'] = {
        'minimalist_design': len(data.get('clickable_links', [])) < 5 and len(data.get('media_files', [])) < 5,
        'portfolio_style': len(data['dates_found']) > 10,
        'potential_archive': bool(data['dates_found']),
        'interactive_elements': data['site_structure'].get('scripts_count', 0) > 2
    }
    
    return analysis

def display_pglang_results(data, analysis=None):
    """
    Display the scraped pgLang data in a readable format
    """
    if 'error' in data:
        print(f"Error: {data['error']}")
        return
    
    print("=" * 60)
    print("PGLANG WEBSITE - SCRAPED INFORMATION")
    print("=" * 60)
    print(f"URL: {data['base_url']}")
    print(f"Title: {data['site_title']}")
    print(f"Scraped: {data['scrape_date']}")
    print()
    
    if data['dates_found']:
        print(f"DATES FOUND ({len(data['dates_found'])}):")
        for i, date in enumerate(data['dates_found'][:20]):  # Show first 20
            print(f"  • {date}")
        if len(data['dates_found']) > 20:
            print(f"  ... and {len(data['dates_found']) - 20} more")
        print()
    
    if data['clickable_links']:
        print("CLICKABLE LINKS:")
        for link in data['clickable_links']:
            external = " (external)" if link['is_external'] else ""
            print(f"  • {link['text']}: {link['url']}{external}")
        print()
    
    if data['media_files']:
        print("MEDIA FILES:")
        for media in data['media_files']:
            print(f"  • {media['type']}: {media['src']}")
        print()
    
    if data['meta_info']:
        print("META INFORMATION:")
        for key, value in data['meta_info'].items():
            if value:
                print(f"  • {key}: {value}")
        print()
    
    print("SITE STRUCTURE:")
    for key, value in data['site_structure'].items():
        print(f"  • {key}: {value}")
    print()
    
    if data['potential_projects']:
        print("POTENTIAL PROJECT PAGES:")
        for project in data['potential_projects']:
            print(f"  • {project['date']}: {project['title']}")
            print(f"    URL: {project['url']}")
            print(f"    Preview: {project['content_preview']}")
        print()
    
    if analysis:
        print("ANALYSIS:")
        if 'timeline_analysis' in analysis:
            print("  Timeline:")
            for key, value in analysis['timeline_analysis'].items():
                print(f"    • {key}: {value}")
        
        if 'activity_patterns' in analysis:
            print("  Activity Patterns:")
            for key, value in analysis['activity_patterns'].items():
                if key != 'monthly_breakdown':
                    print(f"    • {key}: {value}")
        
        if 'site_characteristics' in analysis:
            print("  Site Characteristics:")
            for key, value in analysis['site_characteristics'].items():
                print(f"    • {key}: {value}")
        print()

# Main execution
if __name__ == "__main__":
    url = "https://pg-lang.com/"
    
    print("Scraping pgLang website...")
    scraped_data = scrape_pglang_site(url)
    
    if 'error' not in scraped_data:
        analysis = analyze_pglang_data(scraped_data)
        
        # Display results
        display_pglang_results(scraped_data, analysis)
        
        # Save data
        try:
            with open('pglang_data.json', 'w', encoding='utf-8') as f:
                json.dump({'scraped_data': scraped_data, 'analysis': analysis}, f, indent=2, ensure_ascii=False)
            print("Data saved to pglang_data.json")
        except Exception as e:
            print(f"Failed to save data: {str(e)}")
    else:
        display_pglang_results(scraped_data)
    
    print("\nScraping complete!")