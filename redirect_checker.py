#!/usr/bin/env python3
"""
Redirect Checker - Virtual Tour Automation (IMPROVED)
A Python tool that crawls hotel/property websites and identifies broken virtual tour redirects.
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
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class RedirectChecker:
          """Main class for checking virtual tour redirects."""

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
            print("Error: service_account.json not found")
            return None

    def crawl_property_website(self, url, property_name, max_pages=5):
                  """Crawl a property website and find virtual tour links."""
                  print(f"\nCrawling {property_name}: {url}")
                  print(f"Waiting up to 20 seconds for page to fully load...")

        tour_links = []

        try:
                          options = webdriver.ChromeOptions()
                          options.add_argument('--headless')
                          options.add_argument('--no-sandbox')
                          options.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(
                                  service=Service(ChromeDriverManager().install()),
                                  options=options
            )

            visited_urls = set()
            urls_to_visit = [url]

            while urls_to_visit and len(visited_urls) < max_pages:
                                  current_url = urls_to_visit.pop(0)

                if current_url in visited_urls:
                                          continue

                visited_urls.add(current_url)
                page_num = len(visited_urls)
                print(f"[{page_num}/{max_pages}] {current_url}")

                try:
                                          driver.get(current_url)

                    # WAIT FOR PAGE TO LOAD - Increased to 20 seconds
                                          wait = WebDriverWait(driver, 20)
                                          wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, 'a')))

                    # Give page extra time to render JavaScript
                                          time.sleep(2)

                    # METHOD 1: Look for links with visitingmedia.com in href
                                          print(f"  → Searching for visitingmedia links...")
                                          all_links = driver.find_elements(By.TAG_NAME, 'a')
                                          print(f"  → Found {len(all_links)} total links on page")

                    for link in all_links:
                                                  href = link.get_attribute('href')

                        if href and 'visitingmedia' in href.lower():
                                                          text = link.text.strip() or "Virtual Tour"
                                                          tour_links.append({
                                                              'url': href,
                                                              'text': text,
                                                              'found_on': current_url,
                                                              'property': property_name
                                                          })
                                                          print(f"  ✓ Found tour: {href[:80]}...")

                    # METHOD 2: Look for elements with specific classes or attributes that might indicate tours
                    # (data-tour, tour-icon, 360, etc.)
                    for elem in driver.find_elements(By.XPATH, "//*[contains(@class, '360') or contains(@class, 'tour') or contains(@data-tour, '')]"):
                                                  parent_link = elem.find_elements(By.XPATH, ".//a[@href]")
                                                  for link in parent_link:
                                                                                    href = link.get_attribute('href')
                                                                                    if href and 'visitingmedia' in href.lower():
                                                                                                                          if not any(t['url'] == href for t in tour_links):
                                                                                                                                                                    tour_links.append({
                                                                                                                                                                                                                  'url': href,
                                                                                                                                                                                                                  'text': "Virtual Tour (360 icon)",
                                                                                                                                                                                                                  'found_on': current_url,
                                                                                                                                                                                                                  'property': property_name
                                                                                                                                                                                                              })
                                                                                                                                                                    print(f"  ✓ Found tour (360 icon): {href[:80]}...")
                                                                                                                                                    
                                                        except Exception as e:
                    print(f"  ✗ Error processing {current_url}: {str(e)}")
                    continue

            driver.quit()
            print(f"\n✓ Crawl complete! Found {len(tour_links)} visitingmedia tours")
            return tour_links

except Exception as e:
            print(f"✗ Error crawling {property_name}: {str(e)}")
            try:
                                  driver.quit()
            except:
                pass
            return []

    def check_redirect(self, original_url):
                  """Check where a URL redirects to."""
        try:
                          response = requests.get(original_url, allow_redirects=True, timeout=10)
            final_url = response.url

            # Determine if redirect is GOOD (media library) or BAD
            if '/media' in final_url.lower():
                                  status = 'GOOD'
else:
                status = 'BAD'

            return {
                                  'original_url': original_url,
                                  'redirects_to': final_url,
                                  'status': status,
                                  'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
except Exception as e:
            return {
                                  'original_url': original_url,
                                  'redirects_to': f'Error: {str(e)}',
                                  'status': 'ERROR',
                                  'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def export_to_sheets(self, results):
                  """Export results to Google Sheets - SIMPLIFIED: Only original_url in column A."""
        if not self.service:
                          print("Error: Cannot export without Google Sheets API access")
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

            print(f"✓ Successfully wrote {len(values)} URLs to Google Sheets")
            return result

except HttpError as error:
            print(f"✗ Google Sheets error: {error}")
            return None

    def run(self, property_url, property_name, max_pages=5):
                  """Run the full redirect checker."""
        print("=" * 60)
        print("REDIRECT CHECKER - VIRTUAL TOUR AUTOMATION (IMPROVED)")
        print("=" * 60)

        # Crawl the website
        tour_links = self.crawl_property_website(property_url, property_name, max_pages)

        if not tour_links:
                          print("\n✗ No visitingmedia tour links found on this website.")
            print("   Make sure the URL is correct and has tour links.")
            return

        # Check each redirect
        print(f"\nChecking {len(tour_links)} tour links for redirects...")
        results = []
        for link in tour_links:
                          result = self.check_redirect(link['url'])
            results.append(result)
            print(f"  {result['status']}: {link['text']}")

        # Export to Google Sheets
        self.export_to_sheets(results)

        print("\n✓ Done!")


def main():
          """Main entry point."""
    print("\n" + "=" * 60)
    print("REDIRECT CHECKER - SETUP")
    print("=" * 60)

    sheet_id = input("\nEnter the sheet ID (from Google Sheets URL): ").strip()
    property_url = input("Enter the property website URL: ").strip()
    property_name = input("Enter the property name: ").strip()
    max_pages_input = input("Enter max pages to crawl (default 5): ").strip()
    max_pages = int(max_pages_input) if max_pages_input else 5

    checker = RedirectChecker(sheet_id)
    checker.run(property_url, property_name, max_pages)


if __name__ == '__main__':
          main()
