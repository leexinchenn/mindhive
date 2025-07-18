import requests
from bs4 import BeautifulSoup
import csv
import time
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZusOutletScraper:
    def __init__(self):
        self.base_url = "https://zuscoffee.com/category/store/kuala-lumpur-selangor/"
        self.outlets = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_page_content(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def get_total_pages(self):
        try:
            content = self.get_page_content(self.base_url)
            if not content:
                return 1
            
            soup = BeautifulSoup(content, 'html.parser')
            pagination_links = soup.find_all('a', class_='page-numbers')
            
            if pagination_links:
                page_numbers = []
                for link in pagination_links:
                    text = link.get_text().strip()
                    page_match = re.search(r'Page(\d+)', text)
                    if page_match:
                        page_numbers.append(int(page_match.group(1)))
                    elif text.isdigit():
                        page_numbers.append(int(text))
                
                if page_numbers:
                    max_page = max(page_numbers)
                    logger.info(f"Detected {max_page} pages from pagination")
                    return max_page
                    
            logger.info("No pagination detected, defaulting to 22 pages")
            return 22
            
        except Exception as e:
            logger.error(f"Error getting total pages: {e}")
            return 22
    
    def extract_store_info(self, article):
        try:
            store_info = {
                'name': '',
                'location': '',
                'address': '',
                'direction_link': '',
                'hours': 'Not specified',
                'services': 'Coffee, Food, Beverages'
            }
            
            # Extract store name
            name_element = article.find('p', class_='elementor-heading-title')
            if name_element:
                store_info['name'] = name_element.get_text().strip()
                # Clean up the name
                if store_info['name'].startswith('ZUS Coffee –'):
                    store_info['name'] = store_info['name'].replace('ZUS Coffee –', '').strip()
                elif store_info['name'].startswith('ZUS Coffee -'):
                    store_info['name'] = store_info['name'].replace('ZUS Coffee -', '').strip()
                
                if (store_info['name'].lower() in ['ingredients', '', 'store'] or 
                    len(store_info['name']) < 3):
                    return None
            
            location_element = article.find('h2', class_='elementor-heading-title')
            if location_element:
                location_text = location_element.get_text().strip()
                location_text = location_text.replace(", Store", "").replace(",Store", "")
                store_info['location'] = location_text
            
            # Extract address
            article_text = article.get_text()
            lines = [line.strip() for line in article_text.split('\n') if line.strip()]
            
            if len(lines) >= 3:
                potential_address = lines[2]
                if any(char.isdigit() for char in potential_address) and ',' in potential_address:
                    store_info['address'] = potential_address
                    
                    if "," in potential_address:
                        parts = [part.strip() for part in potential_address.split(",")]
                        for part in reversed(parts):
                            if any(keyword in part.lower() for keyword in ['selangor', 'kuala lumpur', 'wilayah persekutuan']):
                                store_info['location'] = part
                                break
            
            direction_link = article.find('a', string=re.compile(r'Direction', re.I))
            if direction_link:
                store_info['direction_link'] = direction_link.get('href', '')
            
            if not store_info['name'] or len(store_info['name']) < 3:
                return None
                
            return store_info
            
        except Exception as e:
            logger.error(f"Error extracting store info: {e}")
            return None
    
    def scrape_page(self, page_num=1):
        url = f"{self.base_url}page/{page_num}/" if page_num > 1 else self.base_url
        logger.info(f"Scraping page {page_num}: {url}")
        
        try:
            content = self.get_page_content(url)
            if not content:
                return []
            
            soup = BeautifulSoup(content, 'html.parser')
            store_articles = soup.find_all('article')
            
            if not store_articles:
                store_articles = soup.find_all('div', class_=re.compile(r'store|outlet', re.I))
            
            page_outlets = []
            for article in store_articles:
                store_info = self.extract_store_info(article)
                if store_info and store_info['name']:
                    page_outlets.append(store_info)
                    logger.info(f"Found: {store_info['name']}")
            
            return page_outlets
            
        except Exception as e:
            logger.error(f"Error scraping page {page_num}: {e}")
            return []
    
    def clean_outlet_data(self, outlets):
        cleaned_outlets = []
        seen_names = set()
        
        for outlet in outlets:
            if (not outlet['name'] or 
                outlet['name'].lower() in ['ingredients', 'store', ''] or 
                len(outlet['name']) < 3):
                continue
            
            name_key = outlet['name'].lower().strip()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            
            outlet['name'] = outlet['name'].strip()
            outlet['address'] = outlet['address'].strip()
            outlet['location'] = outlet['location'].strip()
            
            cleaned_outlets.append(outlet)
        
        return cleaned_outlets
    
    def scrape_all_outlets(self):
        logger.info("Starting to scrape Zus Coffee outlets...")
        total_pages = self.get_total_pages()
        logger.info(f"Found {total_pages} pages to scrape")
        
        all_outlets = []
        
        for page in range(1, min(total_pages + 1, 100)):
            page_outlets = self.scrape_page(page)
            all_outlets.extend(page_outlets)
            time.sleep(1)
            
            if len(page_outlets) < 2 and page > 1:
                logger.info(f"Few results on page {page}, stopping early")
                break
        
        self.outlets = all_outlets
        self.outlets = self.clean_outlet_data(all_outlets)
        logger.info(f"Scraped {len(all_outlets)} total outlets, {len(self.outlets)} after cleaning")
        return self.outlets
    
    def save_to_csv(self, filename='zus_outlets_kl_selangor.csv'):
        if not self.outlets:
            logger.warning("No outlet data to save")
            return
        
        fieldnames = ['name', 'location', 'address', 'hours', 'services', 'direction_link']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for outlet in self.outlets:
                    clean_outlet = {}
                    for field in fieldnames:
                        clean_outlet[field] = outlet.get(field, '').strip()
                    writer.writerow(clean_outlet)
            
            logger.info(f"Data saved to {filename}")
            print(f"Successfully saved {len(self.outlets)} outlets to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def run(self):
        try:
            outlets = self.scrape_all_outlets()
            self.save_to_csv()
            
            print(f"\n=== SCRAPING SUMMARY ===")
            print(f"Total outlets found: {len(outlets)}")
            print(f"Data saved to: zus_outlets_kl_selangor.csv")
            
            if outlets:
                print(f"\n=== SAMPLE DATA ===")
                for i, outlet in enumerate(outlets[:5]):
                    print(f"{i+1}. {outlet['name']}")
                    print(f"   Address: {outlet['address']}")
                    print(f"   Location: {outlet['location']}")
                    print(f"   Hours: {outlet['hours']}")
                    print(f"   Services: {outlet['services']}")
                    print()
            
        except Exception as e:
            logger.error(f"Error in main execution: {e}")

def main():
    scraper = ZusOutletScraper()
    scraper.run()

if __name__ == "__main__":
    main()
