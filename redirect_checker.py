#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Selenium for JS redirect detection
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Reusable browser instance
_selenium_driver = None

def get_selenium_driver():
    """Get or create a reusable Selenium driver."""
    global _selenium_driver
    if _selenium_driver is None:
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        _selenium_driver = webdriver.Chrome(options=options)
        _selenium_driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
    return _selenium_driver

def close_selenium_driver():
    """Close the Selenium driver."""
    global _selenium_driver
    if _selenium_driver:
        _selenium_driver.quit()
        _selenium_driver = None

class RedirectChecker:
    def __init__(self, base_url, sheet_id=None, credentials_path=None):
        self.results = []
        self.visited_urls = set()
        self.checked_tour_urls = set()  # Deduplicate visitingmedia links
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.crawl_path = self._extract_crawl_path(base_url)
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.sheets_client = None
        
        if sheet_id and credentials_path:
            self._init_sheets()
    
    def _init_sheets(self):
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, scope)
            self.sheets_client = gspread.authorize(creds)
            print("Connected to Google Sheets")
        except Exception as e:
            print(f"Could not connect to Google Sheets: {str(e)}")
            self.sheets_client = None
    
    def _extract_crawl_path(self, url):
        parsed = urlparse(url)
        path = parsed.path
        if path.endswith('.html'):
            path = path.rsplit('/', 1)[0] + '/'
        elif not path.endswith('/'):
            path = path + '/'
        return path
    
    def is_same_domain(self, url):
        domain = urlparse(url).netloc
        return domain == self.base_domain
    
    def is_within_crawl_path(self, url):
        parsed = urlparse(url)
        return parsed.path.startswith(self.crawl_path)
    
    def crawl_website(self, website_url, website_name, max_pages=50):
        print(f"\\nStarting crawl...")
        print(f"Looking for: visitingmedia.com virtual tour iframes")
        print(f"Max pages: {max_pages}\\n")
        
        pages_to_crawl = [website_url]
        pages_crawled = 0
        
        while pages_to_crawl and pages_crawled < max_pages:
            current_url = pages_to_crawl.pop(0)
            
            if current_url in self.visited_urls:
                continue
            
            self.visited_urls.add(current_url)
            pages_crawled += 1
            
            print(f"[{pages_crawled}/{max_pages}] {current_url.split('?')[0][-70:]}")
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                response = requests.get(current_url, headers=headers, timeout=15)

                # Fall back to Selenium if blocked by bot protection
                if response.status_code == 403:
                    print(f"  [403 - retrying with browser...]")
                    driver = get_selenium_driver()
                    driver.get(current_url)
                    time.sleep(3)
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                else:
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                
                # Check for visitingmedia links on THIS page
                self._check_visitingmedia_links(soup, website_name, current_url)
                
                # Only follow links within the property path
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    full_url = urljoin(current_url, href)
                    full_url = full_url.split('#')[0]
                    
                    if (self.is_same_domain(full_url) and 
                        self.is_within_crawl_path(full_url) and 
                        full_url not in self.visited_urls and 
                        len(pages_to_crawl) < max_pages):
                        if full_url not in pages_to_crawl:
                            pages_to_crawl.append(full_url)
                
            except Exception as e:
                print(f"  [Error: {str(e)[:40]}]")
        
        print(f"\\nCrawl complete! Found {len(self.results)} visitingmedia tours")
    
    def _check_visitingmedia_links(self, soup, website_name, page_url):
        """Check for visitingmedia.com links on the current page"""
        found_count = 0

        # Check iframes with src containing visitingmedia
        iframes = soup.find_all('iframe', src=True)
        for iframe in iframes:
            src = iframe.get('src', '')
            if 'visitingmedia.com' in src:
                print(f"    Found visitingmedia iframe")
                self._check_redirect(src, website_name, page_url, "iframe")
                found_count += 1

        # Check elements with data-link attribute containing visitingmedia
        elements_with_data_link = soup.find_all(attrs={'data-link': True})
        for element in elements_with_data_link:
            data_link = element.get('data-link', '')
            if 'visitingmedia.com' in data_link:
                print(f"    Found visitingmedia data-link")
                self._check_redirect(data_link, website_name, page_url, "data-link")
                found_count += 1

        # Check anchor tags with href containing visitingmedia
        anchors = soup.find_all('a', href=True)
        for anchor in anchors:
            href = anchor.get('href', '')
            if 'visitingmedia.com' in href:
                print(f"    Found visitingmedia anchor")
                self._check_redirect(href, website_name, page_url, "anchor")
                found_count += 1

        return found_count
    
    def _check_redirect(self, url, website_name, page_url, source="link"):
        # Deduplicate: skip if we've already checked this exact tour URL
        if url in self.checked_tour_urls:
            print(f"      (duplicate, skipping)")
            return
        self.checked_tour_urls.add(url)

        try:
            # Use Selenium for visitingmedia.com URLs (they use JS redirects)
            if 'visitingmedia.com/tt' in url.lower():
                final_url = self._check_js_redirect(url)
            else:
                # Use requests for direct HTTP redirects
                headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
                final_url = response.url

            status = self._categorize_redirect(final_url)

            self.results.append({
                'website_name': website_name,
                'original_url': url,
                'page_url': page_url,
                'redirects_to': final_url,
                'status': status,
                'source': source,
                'timestamp': datetime.now().isoformat(),
                'error_details': ''
            })

            print(f"      {status}")
        except Exception as e:
            self.results.append({
                'website_name': website_name,
                'original_url': url,
                'page_url': page_url,
                'redirects_to': '',
                'status': 'ERROR',
                'source': source,
                'timestamp': datetime.now().isoformat(),
                'error_details': str(e)
            })

    def _check_js_redirect(self, url):
        """Follow JS redirects using Selenium."""
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(3)  # Wait for JS redirect
        return driver.current_url
    
    def _categorize_redirect(self, url):
        url_lower = url.lower()
        parsed = urlparse(url_lower)

        # Check for a 6-digit asset ID anywhere in the URL (path or query params)
        has_asset_id = bool(re.search(r'\d{6}', url_lower))

        # truetour.app with /media/XXXXXX is always good
        if re.search(r'/media/\d{5,6}', url_lower):
            return 'GOOD'

        # all-assets-share WITH an asset ID param is good (specific asset)
        # all-assets-share WITHOUT an asset ID is bad (generic landing)
        if '/all-assets-share' in url_lower:
            if has_asset_id:
                return 'GOOD'
            return 'BAD REDIRECT'

        # If it's on truetour.app but no /media/ path, it's bad
        if 'truetour.app' in url_lower and '/media/' not in url_lower:
            return 'BAD REDIRECT'

        # If still on visitingmedia.com, the JS redirect didn't work
        if 'visitingmedia.com' in url_lower:
            return 'BAD REDIRECT'

        return 'GOOD'
    
    def save_results(self):
        if not self.results:
            print("No tour links found")
            return
        
        filename = "redirect_checker_results.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        good = sum(1 for r in self.results if r['status'] == 'GOOD')
        bad = sum(1 for r in self.results if r['status'] == 'BAD REDIRECT')
        errors = sum(1 for r in self.results if r['status'] == 'ERROR')
        
        print(f"\\n{'='*60}")
        print(f"Results: {filename}")
        print(f"Total: {len(self.results)} | GOOD: {good} | BAD: {bad} | ERRORS: {errors}")
        print(f"{'='*60}")
        
        if self.sheets_client and self.sheet_id:
            self._write_to_sheets(good, bad, errors)
    
    def _write_to_sheets(self, good, bad, errors):
        try:
            sheet = self.sheets_client.open_by_key(self.sheet_id)
            worksheet = sheet.sheet1

            worksheet.clear()

            # Summary row first
            worksheet.append_row(['Summary', f'Total: {len(self.results)}', f'Good: {good}', f'Bad: {bad}', f'Errors: {errors}', ''])
            worksheet.append_row([])  # blank row

            # Only write BAD/ERROR results - good redirects don't need action
            bad_results = [r for r in self.results if r['status'] != 'GOOD']

            headers = ['Website Name', 'Original URL', 'Page Found On', 'Redirects To', 'Status', 'Timestamp']
            worksheet.append_row(headers)

            for result in bad_results:
                row = [
                    result['website_name'],
                    result['original_url'],
                    result['page_url'],
                    result['redirects_to'],
                    result['status'],
                    result['timestamp']
                ]
                worksheet.append_row(row)

            if bad_results:
                print(f"\\nWrote {len(bad_results)} bad/error results to Google Sheets (skipped {good} good)")
            else:
                print(f"\\nAll {good} redirects are good! Sheet updated with summary only.")
        except Exception as e:
            print(f"\\nCould not write to Google Sheets: {str(e)}")

def main():
    print("="*60)
    print("REDIRECT CHECKER - VISITINGMEDIA FOCUS")
    print("="*60)
    
    website_url = input("\\nEnter property URL: ").strip()
    website_name = input("Enter property name: ").strip()
    max_pages_input = input("Max pages (default 100): ").strip()
    
    if not website_url:
        print("Error: URL required")
        return
    
    if not website_url.startswith(('http://', 'https://')):
        website_url = 'https://' + website_url
    
    if not website_name:
        website_name = website_url
    
    max_pages = 100
    if max_pages_input:
        try:
            max_pages = int(max_pages_input)
        except:
            pass
    
    sheet_id = '18UAf2hhgdS0-tjADyEkRXCPqksGDYPYA67Hd9MYJX1I'
    credentials_path = '/Users/lucaswillett/projects/credentials.json'
    
    checker = RedirectChecker(website_url, sheet_id=sheet_id, credentials_path=credentials_path)
    try:
        checker.crawl_website(website_url, website_name, max_pages=max_pages)
        checker.save_results()
    finally:
        close_selenium_driver()
    print("\\nDone!")

if __name__ == '__main__':
    main()
