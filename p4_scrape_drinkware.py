import csv
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import requests

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def extract_products_from_page(driver, url):
    products = []
    print(f"Loading page: {url}")
    
    try:
        driver.get(url)
        time.sleep(8)
        
        selectors = [
            'article.card-wrapper',
            'div.card-wrapper', 
            'div.grid__item',
            'div.product-card',
            '[data-product-id]'
        ]
        
        product_elements = []
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"Found {len(elements)} products using selector: {selector}")
                product_elements = elements
                break
        
        if not product_elements:
            print("No product elements found, trying to extract from page source...")
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                if 'product' in script.get_text().lower():
                    print("Found potential product data in script tag")
                    try:
                        import json
                        data = json.loads(script.get_text())
                        if isinstance(data, dict) and 'products' in data:
                            return extract_from_json(data['products'])
                    except:
                        continue
        
        for element in product_elements:
            try:
                product_data = extract_product_data(element)
                if product_data and product_data['title']:
                    products.append(product_data)
            except Exception as e:
                print(f"Error extracting product: {e}")
                continue
                
    except Exception as e:
        print(f"Error loading page {url}: {e}")
    
    return products

def extract_product_data(element):
    product = {
        'id': '',
        'title': '',
        'description': '',
        'price': '',
        'compare_price': '',
        'image_url': '',
        'product_url': '',
        'availability': '',
        'tags': ''
    }
    
    try:
        title_selectors = [
            '.card__heading a',
            '.card__heading',
            '.product-card__title',
            'h3 a',
            'h3',
            'a[href*="/products/"]'
        ]
        
        for selector in title_selectors:
            title_elem = element.find_element(By.CSS_SELECTOR, selector)
            if title_elem:
                product['title'] = title_elem.get_attribute('textContent').strip()
                if title_elem.tag_name == 'a':
                    href = title_elem.get_attribute('href')
                    if href:
                        product['product_url'] = href
                break
        
        price_selectors = [
            '.price',
            '.card__price',
            '.product-card__price',
            '[class*="price"]'
        ]
        
        for selector in price_selectors:
            try:
                price_elem = element.find_element(By.CSS_SELECTOR, selector)
                if price_elem:
                    price_text = price_elem.get_attribute('textContent').strip()
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace('RM', '').replace('$', ''))
                    if price_match:
                        product['price'] = price_match.group()
                    break
            except:
                continue
        
        img_selectors = [
            'img',
            '.card__media img',
            '.product-card__image img'
        ]
        
        for selector in img_selectors:
            try:
                img_elem = element.find_element(By.CSS_SELECTOR, selector)
                if img_elem:
                    src = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                    if src:
                        product['image_url'] = src
                        break
            except:
                continue
        
        try:
            product_id = element.get_attribute('data-product-id')
            if not product_id and product['product_url']:
                id_match = re.search(r'/products/([^/?]+)', product['product_url'])
                if id_match:
                    product['id'] = id_match.group(1)
            else:
                product['id'] = product_id or ''
        except:
            pass
        
        product['availability'] = 'available'
        
    except Exception as e:
        print(f"Error extracting product data: {e}")
    
    return product

def extract_from_json(products_json):
    products = []
    
    for product_data in products_json:
        try:
            # Get price from first variant (most products have consistent pricing across variants)
            variants = product_data.get('variants', [])
            price = ''
            compare_price = ''
            availability = 'unavailable'
            
            if variants:
                first_variant = variants[0]
                price = first_variant.get('price', '')
                compare_price = first_variant.get('compare_at_price', '')
                # Check if any variant is available
                availability = 'available' if any(v.get('available', False) for v in variants) else 'unavailable'
            
            product = {
                'id': str(product_data.get('id', '')),
                'title': product_data.get('title', ''),
                'description': BeautifulSoup(product_data.get('body_html', ''), 'html.parser').get_text().strip(),
                'price': price,
                'compare_price': compare_price,
                'image_url': product_data.get('featured_image', ''),
                'product_url': f"https://shop.zuscoffee.com{product_data.get('url', '')}",
                'availability': availability,
                'tags': ', '.join(product_data.get('tags', []))
            }
            products.append(product)
        except Exception as e:
            print(f"Error processing JSON product: {e}")
            continue
    
    return products

def try_json_endpoint():
    endpoints = [
        'https://shop.zuscoffee.com/collections/drinkware/products.json',
        'https://shop.zuscoffee.com/collections/tumbler/products.json',
        'https://shop.zuscoffee.com/products.json'
    ]
    
    for endpoint in endpoints:
        try:
            print(f"Trying JSON endpoint: {endpoint}")
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'products' in data and data['products']:
                    print(f"Successfully fetched {len(data['products'])} products from JSON")
                    return extract_from_json(data['products'])
        except Exception as e:
            print(f"Failed to fetch from {endpoint}: {e}")
            continue
    
    return []

def scrape_zus_drinkware():
    print("Starting ZUS Coffee drinkware scraping...")
    
    products = try_json_endpoint()
    
    if not products:
        print("JSON endpoints failed, using Selenium...")
        
        driver = setup_driver()
        
        try:
            urls = [
                'https://shop.zuscoffee.com/collections/drinkware',
                'https://shop.zuscoffee.com/collections/tumbler',
                'https://shop.zuscoffee.com/collections/all?filter.p.product_type=Tumbler'
            ]
            
            all_products = []
            
            for url in urls:
                page_products = extract_products_from_page(driver, url)
                all_products.extend(page_products)
                time.sleep(2)
            
            seen = set()
            products = []
            for product in all_products:
                identifier = product['id'] or product['title']
                if identifier and identifier not in seen:
                    seen.add(identifier)
                    products.append(product)
            
        finally:
            driver.quit()
    
    print(f"Found {len(products)} unique products")
    
    if products:
        csv_filename = 'zus_drinkware_products.csv'
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'title', 'description', 'price', 'compare_price', 
                         'image_url', 'product_url', 'availability', 'tags']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for product in products:
                writer.writerow(product)
        
        print(f"Products saved to {csv_filename}")
        
        print("\nProduct Summary:")
        for i, product in enumerate(products[:5], 1):
            print(f"{i}. {product['title']} - RM {product['price']}")
        
        if len(products) > 5:
            print(f"... and {len(products) - 5} more products")
    
    else:
        print("No products found!")
    
    return products

if __name__ == "__main__":
    try:
        products = scrape_zus_drinkware()
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"An error occurred: {e}")
