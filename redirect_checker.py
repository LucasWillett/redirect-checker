#!/usr/bin/env python3
"""
Redirect Checker - Virtual Tour Automation
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import gspread
from google.oauth2 import service_account

TOUR_KEYWORDS = ['take a tour', 'truetour', '360 tour', 'virtual tour', 'property tour', 'hotel tour', 'room tour', 'lobby', 'lounge', 'fitness', 'ballroom', 'meeting', 'patio', 'dock', 'suite']

SHEET_ID = os.getenv('GOOGLE_SHEETS_ID')
CREDENTIALS_FILE = 'service_account.json'


class RedirectChecker:
          """Checks virtual tour redirects on property websites."""

    def __init__(self, sheet_id):
                  self.sheet_id = sheet_id
                  self.session = requests.Session()

    def find_tour_links(self, url):
                  """Find all virtual tour links on the page."""
                  tours = []

        try:
                          with sync_playwright() as p:
                                                browser = p.chromium.launch(headless=True)
                                                page = browser.new_page()
                                                page.set_default_timeout(60000)

                try:
                                          page.goto(url, wait_until='domcontentloaded')
                                      except:
                    pass

                                                            import time
                time.sleep(3)

                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, 'html.parser')

            for link in soup.find_all('a', href=True):
                                  href = link['href']
                                  text = link.get_text().lower()

                if 'visitingmedia' in href.lower():
                                          if href not in tours:
                                                                        tours.append(href)

                                      if any(keyword in text for keyword in TOUR_KEYWORDS):
                                                                if 'visitingmedia' in href.lower() or 'matterport' in href.lower():
                                                                                              if href not in tours:
                                                                                                                                tours.append(href)
                                                                                                                
                                                                                  for button in soup.find_all('button'):
                                                                                                        text = button.get_text().lower()
                                                                                                        if any(keyword in text for keyword in TOUR_KEYWORDS):
                                                                                                                                  onclick = button.get('onclick', '') or ''
                                                                                                                                  data_link = button.get('data-link', '') or ''
                                                                                                                                  href = button.get('href', '') or ''
                                                                                                                                  
                    if onclick and 'visitingmedia' in onclick.lower() and onclick not in tours:
                                                  tours.append(onclick)
                    if data_link and data_link not in tours:
                                                  tours.append(data_link)
                    if href and href not in tours:
                                                  tours.append(href)

except Exception as e:
            print(f"Error finding tour links: {str(e)}")

        return tours

    def check_redirects(self, urls):
                  """Check where each URL redirects to."""
        results = []

        for original_url in urls:
                          try:
                                                response = self.session.head(original_url, allow_redirects=True, timeout=10)
                final_url = response.url

                if '/media' in final_url.lower() or 'visitingmedia' in final_url.lower() or 'matterport' in final_url.lower():
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
                  """Export results to Google Sheets using google-auth."""
        try:
                          scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = service_account.Credentials.from_service_account_file(
                                  CREDENTIALS_FILE, scopes=scope)

            client = gspread.authorize(creds)
            sheet = client.open_by_key(self.sheet_id).sheet1

            sheet.clear()

            for idx, result in enumerate(results, start=1):
                                  sheet.update_cell(idx, 1, result['original_url'])

            print(f"✓ Exported {len(results)} tour URLs to Google Sheets")

except Exception as e:
            print(f"Error exporting to sheets: {str(e)}")

    def run(self, property_url):
                  """Main execution flow."""
        print(f"Crawling: {property_url}")

        tour_links = self.find_tour_links(property_url)
        print(f"Found {len(tour_links)} tour links")

        if not tour_links:
                          print("No tour links found!")
            return

        results = self.check_redirects(tour_links)

        print("\n=== REDIRECT CHECK RESULTS ===")
        for result in results:
                          print(f"Original: {result['original_url']}")
            print(f"Final: {result['final_url']}")
            print(f"Status: {result['status']}")
            print()

        if self.sheet_id:
                          self.export_to_sheets(results)
else:
            print("GOOGLE_SHEETS_ID not set. Skipping Google Sheets export.")


def main():
          """Entry point."""
    if len(sys.argv) < 2:
                  print("Usage: python3 redirect_checker.py <property_url>")
        sys.exit(1)

    property_url = sys.argv[1]
    checker = RedirectChecker(os.getenv('GOOGLE_SHEETS_ID'))
    checker.run(property_url)


if __name__ == '__main__':
          main()
