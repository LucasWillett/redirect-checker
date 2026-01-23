#!/usr/bin/env python3
"""
Redirect Checker - Virtual Tour Automation
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

        try:
                      options = webdriver.ChromeOptions()
                      options.add_argument('--headless')
                      options.add_argument('--no-sandbox')
                      options.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(
                              service=Service(ChromeDriverManager().install()),
                              options=options
            )

            driver.get(url)
            WebDriverWait(driver, 10).until(
                              EC.presence_of_all_elements_located((By.TAG_NAME, 'a'))
            )

            # Find virtual tour links
            tour_links = []
            links = driver.find_elements(By.TAG_NAME, 'a')

            for link in links:
                              href = link.get_attribute('href')
                              text = link.text.lower()

                if href and ('visitingmedia' in href.lower() or 
                                                        'tour' in text or 
                                                        '360' in text or
                                                        'virtual' in text):
                                                                              tour_links.append({
                                                                                                        'url': href,
                                                                                                        'text': link.text,
                                                                                                        'found_on': url
                                                                                })

            driver.quit()
            print(f"Found {len(tour_links)} potential tour links")
            return tour_links

except Exception as e:
            print(f"Error crawling {property_name}: {str(e)}")
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

            print(f"Successfully wrote {len(values)} URLs to Google Sheets")
            return result

except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def run(self, property_url, property_name, max_pages=5):
              """Run the full redirect checker."""
        print("=" * 60)
        print("REDIRECT CHECKER - VIRTUAL TOUR AUTOMATION")
        print("=" * 60)

        # Crawl the website
        tour_links = self.crawl_property_website(property_url, property_name, max_pages)

        if not tour_links:
                      print("\nNo tour links found.")
                      return

        # Check each redirect
        print(f"\nChecking {len(tour_links)} tour links...")
        results = []
        for link in tour_links:
                      result = self.check_redirect(link['url'])
                      results.append(result)
                      print(f"  {link['url']}: {result['status']}")

        # Export to Google Sheets
        self.export_to_sheets(results)

        print("\nDone!")


def main():
      """Main entry point."""
    print("Enter the sheet ID (from Google Sheets URL): ", end="")
    sheet_id = input().strip()

    print("\nEnter the property website URL: ", end="")
    property_url = input().strip()

    print("Enter the property name: ", end="")
    property_name = input().strip()

    print("Enter max pages to crawl (default 5): ", end="")
    max_pages_input = input().strip()
    max_pages = int(max_pages_input) if max_pages_input else 5

    checker = RedirectChecker(sheet_id)
    checker.run(property_url, property_name, max_pages)


if __name__ == '__main__':
      main()
