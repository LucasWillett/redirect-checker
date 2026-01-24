#!/usr/bin/env python3
"""
Redirect Checker - Virtual Tour Automation (UNIVERSAL v3 - FIXED JS RENDERING)
Detects and checks virtual tours across multiple platforms:
- Visiting Media (direct links + generic tour buttons)
- Embedded tours (Matterport, etc. via buttons/divs)
- Multi-platform support
- Generic "Take a Tour", "360 Tour", "Virtual Tour", etc. link detection
"""

import os
import sys
import time
import requests
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class RedirectChecker:
          """Universal virtual tour detector and redirect checker."""

    # Keywords that indicate a tour link
          TOUR_KEYWORDS = [
              'take a tour', 'truetour', '360', 'virtual tour', 'virtual view', '3d tour', '3d model',
              'virtual walk', 'interactive tour', 'tour now', 'explore', 'view tour',
              'hotel tour', 'room tour', 'tour the property', 'view property', 'see inside',
              'view in 3d', 'virtual experience', 'virtual property'
          ]

    def __init__(self, sheet_id):
                  """Initialize the redirect checker."""
                  self.sheet_id = sheet_id
                  self.tours_found = []
                  self.service = self._get_sheets_service()

    def _get_sheets_service(self):
                  """Get Google Sheets API service."""
                  try:
                                    creds = Credentials.from_service_account_file(
                                                          'service_account.json',
                                                          scopes=['https://www.googleapis.com/auth/spreadsheets']
                                    )
                                    return build('sheets', 'v4', credentials=creds)
except FileNotFoundError:
            print("✗ Error: service_account.json not found")
            return None

    def _is_tour_link(self, text):
                  """Check if link text matches tour keywords."""
                  text_lower = text.lower().strip()
                  return any(keyword in text_lower for keyword in self.TOUR_KEYWORDS)

    def _create_driver(self):
                  """Create a properly configured Chrome driver for JS rendering."""
                  options = Options()
                  # CRITICAL FIX: Don't use headless mode or disable JS
                  options.add_argument('--headless=new')  # New headless mode works better with JS
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')  # Keep this for memory stability
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')  # Disable GPU to avoid issues

        try:
                          driver = webdriver.Chrome(
                                                service=Service(ChromeDriverManager().install()),
                                                options=options
                          )
                          return driver
except Exception as e:
                  print(f"✗ Failed to create Chrome driver: {str(e)}")
                  return None

    def crawl_property_website(self, url, property_name, max_pages=5):
                  """Crawl and find virtual tours using multiple detection methods."""
                  print(f"\n{'='*60}")
                  print(f"Crawling: {property_name}")
                  print(f"URL: {url}")
                  print(f"{'='*60}")

        tour_links = []
        driver = self._create_driver()

        if not driver:
                          print("✗ Could not create Chrome driver")
                          return []

        try:
                          visited_urls = set()
                          urls_to_visit = [url]

            while urls_to_visit and len(visited_urls) < max_pages:
                                  current_url = urls_to_visit.pop(0)

                if current_url in visited_urls:
                                          continue

                visited_urls.add(current_url)
                page_num = len(visited_urls)
                print(f"\n[{page_num}/{max_pages}] {current_url}")

                try:
                                          driver.get(current_url)

                    # CRITICAL: Wait for links to load with much longer timeout
                                          wait = WebDriverWait(driver, 30)
                                          wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, 'a')))

                    # Extra wait for any lazy-loaded content
                                          time.sleep(5)

                    print(f"  → Scanning for virtual tours...")

                    # METHOD 1: Direct visitingmedia links in <a> tags
                    print(f"    • Checking for visitingmedia links...")
                    all_links = driver.find_elements(By.TAG_NAME, 'a')
                    print(f"    → Found {len(all_links)} total links on page")
                    visitingmedia_count = 0

                    for link in all_links:
                                                  try:
                                                                                    href = link.get_attribute('href')
                                                                                    text = link.text.strip()

                            if href and 'visitingmedia' in href.lower():
                                                                  tour_links.append({
                                                                                                            'url': href,
                                                                                                            'text': text or "Virtual Tour",
                                                                                                            'found_on': current_url,
                                                                                                            'property': property_name,
                                                                                                            'type': 'visitingmedia_link'
                                                                        })
                                                                  visitingmedia_count += 1
                                                                  print(f"      ✓ Found: {text or 'visitingmedia tour'}")
except Exception as e:
                            pass

                    if visitingmedia_count > 0:
                                                  print(f"    ✓ Found {visitingmedia_count} visitingmedia link(s)")
else:
                              print(f"    • No direct visitingmedia links found")

                    # METHOD 2: Generic "Take a Tour" style links
                          print(f"    • Checking for generic tour links...")
                    generic_tour_links = 0

                    for link in all_links:
                                                  try:
                                                                                    href = link.get_attribute('href')
                                                                                    text = link.text.strip()

                            # Skip if already found as visitingmedia
                                                      if href and 'visitingmedia' in href.lower():
                                                                                            continue

                            # Check if link text matches tour keywords
                            if href and self._is_tour_link(text):
                                                                  # Only include if it looks like a real URL (not just navigation)
                                                                  if href.startswith('http') or href.startswith('/'):
                                                                                                            tour_links.append({
                                                                                                                                                          'url': href,
                                                                                                                                                          'text': text,
                                                                                                                                                          'found_on': current_url,
                                                                                                                                                          'property': property_name,
                                                                                                                                                          'type': 'generic_tour_link'
                                                                                                                  })
                                                                                                            generic_tour_links += 1
                                                                                                            print(f"      ✓ Found: {text}")
                                  except Exception as e:
                            pass

                    if generic_tour_links > 0:
                                                  print(f"    ✓ Found {generic_tour_links} generic tour link(s)")
else:
                        print(f"    • No generic tour links found")

                    # METHOD 3: Button elements with tour-related text
                    print(f"    • Checking for tour buttons...")
                    buttons = driver.find_elements(By.TAG_NAME, 'button')
                    tour_buttons = 0

                    for btn in buttons:
                                                  try:
                                                                                    text = btn.text.strip()
                                                                                    if self._is_tour_link(text):
                                                                                                                          tour_buttons += 1
                                                                                                                          tour_links.append({
                                                                                                                              'url': f"BUTTON:{text}",
                                                                                                                              'text': text,
                                                                                                                              'found_on': current_url,
                                                                                                                              'property': property_name,
                                                                                                                              'type': 'embedded_tour_button'
                                                                                                                                })
                                                                                                                          print(f"      ✓ Found button: {text}")
                                                        except Exception as e:
                            pass

                    if tour_buttons > 0:
                                                  print(f"    ✓ Found {tour_buttons} tour button(s)")
else:
                        print(f"    • No tour buttons found")

except Exception as e:
                    print(f"  ✗ Error processing {current_url}: {str(e)}")
                    continue

            driver.quit()
            print(f"\n{'='*60}")
            print(f"✓ Crawl Complete: Found {len(tour_links)} total tours")
            print(f"{'='*60}")
            return tour_links

except Exception as e:
            print(f"✗ Critical error crawling {property_name}: {str(e)}")
            try:
                                  driver.quit()
            except:
                pass
            return []

    def check_redirect(self, tour_url):
                  """Check where a URL redirects to."""
        # Skip embedded/button tours - they don't redirect
        if tour_url.startswith('BUTTON:') or tour_url.startswith('EMBEDDED:'):
                          return {
                                                'original_url': tour_url,
                                                'redirects_to': 'N/A (Embedded Tour)',
                                                'status': 'EMBEDDED',
                                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                          }

        try:
                          response = requests.get(tour_url, allow_redirects=True, timeout=10)
            final_url = response.url

            # Determine redirect status
            if '/media' in final_url.lower():
                                  status = 'GOOD'
else:
                status = 'BAD'

            return {
                                  'original_url': tour_url,
                                  'redirects_to': final_url,
                                  'status': status,
                                  'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
except Exception as e:
            return {
                                  'original_url': tour_url,
                                  'redirects_to': f'Error: {str(e)}',
                                  'status': 'ERROR',
                                  'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def export_to_sheets(self, results):
                  """Export results to Google Sheets - SIMPLIFIED: Only original_url in column A."""
        if not self.service:
                          print("✗ Error: Cannot export without Google Sheets API access")
            return

        try:
                          # Prepare data for Google Sheets (only original_url)
                          values = []
            for result in results:
                                  values.append([result['original_url']])

            # Clear existing data
            self.service.spreadsheets().values().clear(
                                  spreadsheetId=self.sheet_id,
                                  range='Sheet1'
            ).execute()

            # Write new data
            body = {'values': values}
            result = self.service.spreadsheets().values().update(
                                  spreadsheetId=self.sheet_id,
                                  range='Sheet1!A1',
                                  valueInputOption='RAW',
                                  body=body
            ).execute()

            print(f"\n✓ Successfully wrote {len(values)} URLs to Google Sheets")
            return result

except HttpError as error:
            print(f"✗ Google Sheets error: {error}")
            return None

    def run(self, property_url, property_name, max_pages=5):
                  """Run the full redirect checker."""
        print("\n" + "="*60)
        print("REDIRECT CHECKER - UNIVERSAL VIRTUAL TOUR DETECTION v3")
        print("="*60)

        # Crawl the website
        tour_links = self.crawl_property_website(property_url, property_name, max_pages)

        if not tour_links:
                          print("\n✗ No tours found on this website.")
            return

        # Check each redirect
        print(f"\nChecking {len(tour_links)} tour(s) for redirects...")
        results = []
        bad_redirects = 0

        for link in tour_links:
                          result = self.check_redirect(link['url'])
            results.append(result)
            status_symbol = "✓" if result['status'] == 'GOOD' else "✗" if result['status'] == 'BAD' else "○"
            print(f"  {status_symbol} [{result['status']}] {link['text']}")

            if result['status'] == 'BAD':
                                  bad_redirects += 1

        # Export to Google Sheets
        self.export_to_sheets(results)

        if bad_redirects > 0:
                          print(f"\n⚠️  WARNING: Found {bad_redirects} bad redirect(s)!")

        print(f"\n✓ Analysis complete!")


def main():
          """Main entry point."""
    print("\n" + "="*60)
    print("REDIRECT CHECKER - SETUP")
    print("="*60)

    sheet_id = input("\nEnter the sheet ID (from Google Sheets URL): ").strip()
    property_url = input("Enter the property website URL: ").strip()
    property_name = input("Enter the property name: ").strip()
    max_pages_input = input("Enter max pages to crawl (default 5): ").strip()
    max_pages = int(max_pages_input) if max_pages_input else 5

    checker = RedirectChecker(sheet_id)
    checker.run(property_url, property_name, max_pages)


if __name__ == '__main__':
          main()
