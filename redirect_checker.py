#!/usr/bin/env python3
"""
Redirect Checker - Virtual Tour Automation
Crawls hotel/property websites and identifies broken virtual tour redirects.
"""

import os
import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from urllib.parse import urljoin, urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOUR_KEYWORDS = [
      'take a tour',
      'truetour',
      '360 tour',
      'virtual tour',
      'property tour',
      'hotel tour',
      'room tour',
      'lobby',
      'lounge'
]

SHEET_ID = os.getenv('GOOGLE_SHEETS_ID')
CREDENTIALS_FILE = 'service_account.json'


class RedirectChecker:
      """Checks virtual tour redirects on property websites."""

    def __init__(self, sheet_id):
              self.sheet_id = sheet_id
              self.session = requests.Session()
              self.session.headers.update({
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
              })

    def get_chrome_driver(self):
              """Initialize Chrome WebDriver with optimized settings for JS rendering."""
              chrome_options = Options()
              chrome_options.add_argument('--headless=new')
              chrome_options.add_argument('--disable-blink-features=AutomationControlled')
              chrome_options.add_argument('--disable-dev-shm-usage')
              chrome_options.add_argument('--start-maximized')
              chrome_options.add_argument('--disable-gpu')
              chrome_options.add_argument('--no-sandbox')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def find_tour_links(self, url):
              """Find all virtual tour links on the page using multiple detection methods."""
              tours = []
              driver = None

        try:
                      driver = self.get_chrome_driver()
                      driver.get(url)

            # Wait for page to load and JS to render
                      try:
                                        WebDriverWait(driver, 30).until(
                                                              EC.presence_of_all_elements_located((By.TAG_NAME, 'a'))
                                        )
        except Exception:
                          pass

            # Additional wait for JS rendering
                      time.sleep(5)

            # Get the current page HTML
            page_source = driver.page_source

            # Method 1: Find all <a> tags with visitingmedia links
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                              try:
                                                    href = link.get_attribute('href')
                                                    if href and 'visitingmedia' in href.lower():
                                                                              if href not in tours:
                                                                                                            tours.append(href)
                                                      except Exception:
                                                                            pass

                          # Method 2: Find all <button> tags with tour keywords
                          buttons = driver.find_elements(By.TAG_NAME, 'button')
            for button in buttons:
                              try:
                                                    text = button.text.lower()
                                                    if any(keyword in text for keyword in TOUR_KEYWORDS):
                                                                              onclick = button.get_attribute('onclick')
                                                                              data_href = button.get_attribute('data-href')
                                                                              href = button.get_attribute('href')

                                                        if onclick and 'visitingmedia' in onclick.lower():
                                                                                      if onclick not in tours:
                                                                                                                        tours.append(onclick)
                                                          elif data_href:
                            if data_href not in tours:
                                                              tours.append(data_href)
elif href:
                            if href not in tours:
                                                              tours.append(href)
except Exception:
                    pass

            # Method 3: Find generic tour links (like "Take a Tour" links)
            for link in links:
                              try:
                                                    text = link.text.lower()
                    href = link.get_attribute('href')
                    if href and any(keyword in text for keyword in TOUR_KEYWORDS):
                                              if 'visitingmedia' in href.lower() or 'matterport' in href.lower():
                                                                            if href not in tours:
                                                                                                              tours.append(href)
                                                except Exception:
                    pass

            # Method 4: Find elements with data attributes containing tour URLs
            all_elements = driver.find_elements(By.XPATH, '//*[@data-tour-url or @data-href or @data-visitingmedia]')
            for element in all_elements:
                              try:
                                                    tour_url = element.get_attribute('data-tour-url')
                    data_href = element.get_attribute('data-href')
                    data_vm = element.get_attribute('data-visitingmedia')

                    if tour_url and tour_url not in tours:
                                              tours.append(tour_url)
                    if data_href and data_href not in tours:
                                              tours.append(data_href)
                    if data_vm and data_vm not in tours:
                                              tours.append(data_vm)
except Exception:
                    pass

            # Method 5: Find Matterport references
            for link in links:
                              try:
                                                    href = link.get_attribute('href')
                    if href and 'matterport' in href.lower():
                                              if href not in tours:
                                                                            tours.append(href)
except Exception:
                    pass

except Exception as e:
            print(f"Error finding tour links: {str(e)}")

finally:
            if driver:
                              driver.quit()

        return tours

    def check_redirects(self, urls):
              """Check where each URL redirects to."""
        results = []

        for original_url in urls:
                      try:
                                        response = self.session.head(original_url, allow_redirects=True, timeout=10)
                                        final_url = response.url

                          # Classify as GOOD or BAD redirect
                                        if '/media' in final_url.lower() or 'visitingmedia' in final_url.lower():
                                                              status = 'GOOD'
else:
                      status = 'BAD'

                results.append({
                                      'original_url': original_url,
                                      'final_url': final_url,
                                      'status': status
                })

except Exception as e:
                results.append({
                                      'original_url': original_url,
                                      'final_url': 'ERROR',
                                      'status': 'ERROR'
                })

        return results

    def export_to_sheets(self, results):
              """Export results to Google Sheets - only original_url to column A."""
              try:
                            scope = ['https://spreadsheets.google.com/auth/spreadsheets']
                            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
                            client = gspread.authorize(creds)
                            sheet = client.open_by_key(self.sheet_id).sheet1

                  # Clear existing data
                            sheet.clear()

            # Write only original_url to column A
            for idx, result in enumerate(results, start=1):
                              sheet.update_cell(idx, 1, result['original_url'])

            print(f"Exported {len(results)} tour URLs to Google Sheets")

except Exception as e:
            print(f"Error exporting to sheets: {str(e)}")

    def run(self, property_url):
              """Main execution flow."""
        print(f"Crawling: {property_url}")

        # Step 1: Find tour links
        tour_links = self.find_tour_links(property_url)
        print(f"Found {len(tour_links)} tour links")

        if not tour_links:
                      print("No tour links found!")
                      return

        # Step 2: Check redirects
        results = self.check_redirects(tour_links)

        # Step 3: Display results
        print("\n=== REDIRECT CHECK RESULTS ===")
        for result in results:
                      print(f"Original: {result['original_url']}")
                      print(f"Final: {result['final_url']}")
                      print(f"Status: {result['status']}")
                      print()

        # Step 4: Export to Google Sheets
        if SHEET_ID:
                      self.export_to_sheets(results)
else:
            print("GOOGLE_SHEETS_ID not set. Skipping Google Sheets export.")


def main():
      """Entry point."""
    if len(sys.argv) < 2:
              print("Usage: python3 redirect_checker.py <property_url>")
        print("Example: python3 redirect_checker.py https://www.thelorenhotels.com/austin/accommodations")
        sys.exit(1)

    property_url = sys.argv[1]

    checker = RedirectChecker(SHEET_ID)
    checker.run(property_url)


if __name__ == '__main__':
      main()
