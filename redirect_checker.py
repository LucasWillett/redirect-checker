#!/usr/bin/env python3
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

class RedirectChecker:
    # Minimum page size in chars - pages smaller than this are likely blocked
    MIN_PAGE_SIZE = 50000

    def __init__(self, base_url, sheet_id=None, credentials_path=None):
        self.results = []
        self.visited_urls = set()
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.crawl_path = self._extract_crawl_path(base_url)
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.sheets_client = None
        self.worksheet = None
        self.playwright = None
        self.browser = None
        self.page = None
        self.manual_review_sites = []  # Sites that appear to block automation
        self.properties_processed = 0
        self.total_good = 0
        self.total_bad = 0
        self.total_errors = 0
        self.last_sheet_row = 2  # Track last written row (after header)

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

    def _init_output_sheet(self):
        """Initialize output sheet with headers for incremental writing"""
        if not self.sheets_client or not self.sheet_id:
            return
        try:
            sheet = self.sheets_client.open_by_key(self.sheet_id)
            self.worksheet = sheet.sheet1
            self.worksheet.clear()
            # Write headers
            headers = ['Property Name', 'Original URL', 'Page Found On', 'Redirects To', 'Status', 'Timestamp']
            self.worksheet.append_row(headers)
            self.last_sheet_row = 2
            print("Output sheet initialized")
        except Exception as e:
            print(f"Could not initialize output sheet: {str(e)}")

    def _append_to_sheet(self, results_to_add):
        """Append new problem results to the sheet incrementally"""
        if not self.worksheet:
            return
        try:
            # Only add BAD REDIRECT, ERROR results
            problem_results = [r for r in results_to_add if r['status'] in ['BAD REDIRECT', 'ERROR']]
            for result in problem_results:
                row = [
                    result['website_name'],
                    result['original_url'],
                    result['page_url'],
                    result['redirects_to'],
                    result['status'],
                    result['timestamp']
                ]
                self.worksheet.append_row(row)
                self.last_sheet_row += 1
        except Exception as e:
            print(f"Could not append to sheet: {str(e)}")

    def _update_sheet_summary(self):
        """Update the summary in the sheet (adds blocked sites at the end)"""
        if not self.worksheet:
            return
        try:
            # Add blocked sites
            if self.manual_review_sites:
                self.worksheet.append_row([])
                self.worksheet.append_row(['--- BLOCKED SITES (Manual Review) ---', '', '', '', '', ''])
                for site in self.manual_review_sites:
                    self.worksheet.append_row([
                        site['website_name'],
                        site['url'],
                        '',
                        site['reason'],
                        'BLOCKED',
                        site['timestamp']
                    ])

            # Add summary at the bottom
            self.worksheet.append_row([])
            self.worksheet.append_row([
                f'SUMMARY: {self.properties_processed} properties processed',
                f'GOOD: {self.total_good}',
                f'BAD: {self.total_bad}',
                f'ERRORS: {self.total_errors}',
                f'BLOCKED: {len(self.manual_review_sites)}',
                datetime.now().isoformat()
            ])
        except Exception as e:
            print(f"Could not update sheet summary: {str(e)}")

    def _init_browser(self):
        """Initialize Playwright browser"""
        self.playwright = sync_playwright().start()
        # Use Firefox - better at bypassing bot detection
        self.browser = self.playwright.firefox.launch(headless=True)
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
        )
        self.page = self.context.new_page()

    def _close_browser(self):
        """Close Playwright browser"""
        if self.page:
            self.page.close()
        if hasattr(self, 'context') and self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

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
        print(f"\nStarting crawl...")
        print(f"Looking for: 'Virtual Tour' / '3D Tour' links + visitingmedia.com / truetour.app")
        print(f"Max pages: {max_pages}\n")

        self._init_browser()

        try:
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
                    # Use Playwright to load the page (handles JS)
                    self.page.goto(current_url, wait_until='load', timeout=45000)
                    time.sleep(2)  # Extra wait for any late-loading content

                    # Get the rendered HTML
                    html_content = self.page.content()

                    # Check if page appears to be blocked/bot-detected
                    if self._is_page_blocked(html_content, current_url, website_name):
                        print(f"  [BLOCKED: This site has bot detection - flagged for manual review]")
                        continue

                    soup = BeautifulSoup(html_content, 'html.parser')

                    # Check for tour links on THIS page
                    self._check_tour_links(soup, website_name, current_url)

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

                    # Rate limiting delay
                    time.sleep(2)

                except Exception as e:
                    print(f"  [Error: {str(e)[:50]}]")

            print(f"\nCrawl complete! Found {len(self.results)} tour links")
        finally:
            self._close_browser()

    def _is_page_blocked(self, html_content, url, website_name):
        """Check if the page appears to be blocking automation"""
        page_size = len(html_content)

        # Check 1: Page is suspiciously small
        if page_size < self.MIN_PAGE_SIZE:
            # Check for common bot detection signs
            html_lower = html_content.lower()
            bot_indicators = [
                'captcha',
                'please verify',
                'access denied',
                'blocked',
                'robot',
                'automated'
            ]

            # If small AND has bot indicators, definitely blocked
            is_blocked = any(indicator in html_lower for indicator in bot_indicators)

            # If just small and missing typical page elements, likely blocked
            if not is_blocked:
                missing_content = (
                    '<main' not in html_lower and
                    '<article' not in html_lower and
                    'class="content"' not in html_lower and
                    len(html_content) < 20000  # Very small
                )
                is_blocked = missing_content

            if is_blocked or page_size < 20000:
                self.manual_review_sites.append({
                    'website_name': website_name,
                    'url': url,
                    'reason': f'Page size only {page_size} chars - likely bot detection',
                    'timestamp': datetime.now().isoformat()
                })
                return True

        return False

    def _is_tour_domain(self, url):
        """Check if URL is a visitingmedia or truetour link"""
        return 'visitingmedia.com' in url or 'truetour.app' in url

    def _has_tour_text(self, element):
        """Check if element or its children contain tour-related phrases (case insensitive)"""
        # Check visible text
        text = element.get_text().lower()
        if 'virtual tour' in text or '3d tour' in text:
            return True

        # Check element attributes
        for attr in ['title', 'aria-label', 'alt', 'data-title']:
            val = element.get(attr, '').lower()
            if 'virtual tour' in val or '3d tour' in val:
                return True

        # Check images inside the element
        for img in element.find_all('img'):
            alt = img.get('alt', '').lower()
            title = img.get('title', '').lower()
            if 'virtual tour' in alt or '3d tour' in alt or 'virtual tour' in title or '3d tour' in title:
                return True

        return False

    def _check_tour_links(self, soup, website_name, page_url):
        """Check for virtual tour links on the current page"""
        found_count = 0
        checked_urls = set()  # Avoid checking same URL twice

        # Check iframes with src containing tour domains
        iframes = soup.find_all('iframe', src=True)
        for iframe in iframes:
            src = iframe.get('src', '')
            if self._is_tour_domain(src) and src not in checked_urls:
                checked_urls.add(src)
                print(f"    Found tour iframe")
                self._check_redirect(src, website_name, page_url, "iframe")
                found_count += 1

        # Check elements with data-link attribute containing tour domains
        elements_with_data_link = soup.find_all(attrs={'data-link': True})
        for element in elements_with_data_link:
            data_link = element.get('data-link', '')
            if self._is_tour_domain(data_link) and data_link not in checked_urls:
                checked_urls.add(data_link)
                print(f"    Found tour data-link")
                self._check_redirect(data_link, website_name, page_url, "data-link")
                found_count += 1

        # Check anchor tags - multiple approaches:
        anchors = soup.find_all('a', href=True)
        for anchor in anchors:
            href = anchor.get('href', '')
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue

            # Convert relative URLs to absolute
            if not href.startswith(('http://', 'https://')):
                href = urljoin(page_url, href)

            if href in checked_urls:
                continue

            # Approach 1: href contains tour domain
            if self._is_tour_domain(href):
                checked_urls.add(href)
                print(f"    Found tour anchor (by domain)")
                self._check_redirect(href, website_name, page_url, "anchor")
                found_count += 1

            # Approach 2: link text/attributes contain "virtual tour" or "3d tour"
            elif self._has_tour_text(anchor):
                checked_urls.add(href)
                print(f"    Found tour link (by text): {href[:60]}...")
                self._check_redirect(href, website_name, page_url, "tour-text")
                found_count += 1

        # Approach 3: Find links inside elements with tour-related classes
        tour_containers = soup.find_all(class_=lambda c: c and ('virtual-tour' in c.lower() or '3d-tour' in c.lower() or 'tour-tag' in c.lower()))
        for container in tour_containers:
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if href and href not in checked_urls:
                    checked_urls.add(href)
                    print(f"    Found tour link (by container class): {href[:60]}...")
                    self._check_redirect(href, website_name, page_url, "tour-class")
                    found_count += 1

        return found_count

    def _check_redirect(self, url, website_name, page_url, source="link"):
        """Follow the redirect using Playwright to get the final URL"""
        try:
            # Create a new page for redirect checking to not interfere with crawling
            redirect_page = self.context.new_page()
            try:
                redirect_page.goto(url, wait_until='domcontentloaded', timeout=15000)
                final_url = redirect_page.url
            finally:
                redirect_page.close()

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
            print(f"      ERROR: {str(e)[:40]}")

    def _categorize_redirect(self, url):
        url_lower = url.lower()

        if '/all-assets-share' in url_lower:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if 'asset' not in query_params:
                return 'BAD REDIRECT'

        return 'GOOD'

    def save_results(self):
        if not self.results and not self.manual_review_sites:
            print("No tour links found")
            return

        # Save tour link results
        filename = "redirect_checker_results.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)

        good = sum(1 for r in self.results if r['status'] == 'GOOD')
        bad = sum(1 for r in self.results if r['status'] == 'BAD REDIRECT')
        errors = sum(1 for r in self.results if r['status'] == 'ERROR')
        manual_review = len(self.manual_review_sites)

        print(f"\n{'='*60}")
        print(f"Results: {filename}")
        print(f"Total: {len(self.results)} | GOOD: {good} | BAD: {bad} | ERRORS: {errors}")

        # Save and report manual review sites
        if self.manual_review_sites:
            review_filename = "manual_review_sites.json"
            with open(review_filename, 'w') as f:
                json.dump(self.manual_review_sites, f, indent=2)

            print(f"\n{'!'*60}")
            print(f"MANUAL REVIEW NEEDED: {manual_review} site(s)")
            print(f"{'!'*60}")
            print(f"\nThese sites have anti-bot protection that prevents automated")
            print(f"crawling. This is common with large enterprise sites (Hyatt,")
            print(f"Marriott, Hilton, etc.) that use aggressive bot detection.")
            print(f"\nThis is NOT an error with the redirect checker - these sites")
            print(f"intentionally block automated tools. You'll need to check")
            print(f"these manually in a web browser.")
            print(f"\nBlocked sites saved to: {review_filename}")
            print(f"")
            for site in self.manual_review_sites:
                print(f"  - {site['url']}")
                print(f"    ({site['reason']})")

        print(f"{'='*60}")

        if self.sheets_client and self.sheet_id:
            self._write_to_sheets(good, bad, errors)

    def _write_to_sheets(self, good, bad, errors):
        try:
            sheet = self.sheets_client.open_by_key(self.sheet_id)
            worksheet = sheet.sheet1

            worksheet.clear()

            # Only write BAD REDIRECT and ERROR results - no need to show working links
            problem_results = [r for r in self.results if r['status'] in ['BAD REDIRECT', 'ERROR']]

            headers = ['Website Name', 'Original URL', 'Page Found On', 'Redirects To', 'Status', 'Timestamp']
            worksheet.append_row(headers)

            for result in problem_results:
                row = [
                    result['website_name'],
                    result['original_url'],
                    result['page_url'],
                    result['redirects_to'],
                    result['status'],
                    result['timestamp']
                ]
                worksheet.append_row(row)

            # Add manual review sites at the bottom
            if self.manual_review_sites:
                worksheet.append_row([])  # Empty row separator
                worksheet.append_row(['--- BLOCKED SITES (Manual Review Needed) ---', '', '', '', '', ''])
                for site in self.manual_review_sites:
                    worksheet.append_row([
                        site['website_name'],
                        site['url'],
                        '',
                        '',
                        'BLOCKED',
                        site['timestamp']
                    ])

            total_problems = len(problem_results) + len(self.manual_review_sites)
            print(f"\nWrote {total_problems} problem links to Google Sheets (BAD: {bad}, ERRORS: {errors}, BLOCKED: {len(self.manual_review_sites)})")
        except Exception as e:
            print(f"\nCould not write to Google Sheets: {str(e)}")

def run_single_mode(credentials_path, output_sheet_id):
    """Run checker on a single URL (interactive mode)"""
    website_url = input("\nEnter property URL: ").strip()
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

    checker = RedirectChecker(website_url, sheet_id=output_sheet_id, credentials_path=credentials_path)
    checker.crawl_website(website_url, website_name, max_pages=max_pages)
    checker.save_results()


def run_batch_mode(credentials_path, input_sheet_id, output_sheet_id, max_pages=10, start_row=1, row_limit=None):
    """Run checker on multiple URLs from a Google Sheet

    Expected input sheet format:
    - Column A: Property name
    - Column B: URL 1 (required)
    - Column C: URL 2 (optional)
    - Column D: URL 3 (optional)

    Args:
        start_row: Row number to start from (1-indexed, after header)
        row_limit: Max number of properties to process (None = all)
    """
    print("\nBatch mode: Reading properties from Google Sheet...")

    # Connect to Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)

    # Read input sheet
    input_sheet = client.open_by_key(input_sheet_id)
    input_worksheet = input_sheet.sheet1
    all_rows = input_worksheet.get_all_values()

    # Skip header row if present
    header_offset = 0
    if all_rows and all_rows[0][0].lower() in ['property', 'name', 'property name', 'hotel', 'account name', 'account']:
        header_offset = 1
        print(f"Detected header row, skipping")

    # Calculate which rows to process
    data_rows = all_rows[header_offset:]
    total_rows = len(data_rows)

    # Apply start_row (1-indexed from user perspective)
    actual_start = max(0, start_row - 1)
    data_rows = data_rows[actual_start:]

    # Apply row limit
    if row_limit:
        data_rows = data_rows[:row_limit]

    print(f"Total properties in sheet: {total_rows}")
    print(f"Processing rows {actual_start + 1} to {actual_start + len(data_rows)}")
    print(f"Properties to process: {len(data_rows)}\n")

    # Create checker with output sheet
    # Use a dummy base_url since we'll be processing multiple
    checker = RedirectChecker("https://example.com", sheet_id=output_sheet_id, credentials_path=credentials_path)

    # Initialize output sheet with headers
    checker._init_output_sheet()

    # Process each property
    for i, row in enumerate(data_rows):
        if len(row) < 2:
            continue

        property_name = row[0].strip() if row[0] else f"Property {i+1}"

        # Get URLs from columns B, C, D (indices 1, 2, 3)
        urls = []
        for col_idx in [1, 2, 3]:
            if col_idx < len(row) and row[col_idx].strip():
                url = row[col_idx].strip()
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                urls.append(url)

        if not urls:
            print(f"[{i+1}/{len(data_rows)}] {property_name}: No URLs found, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(data_rows)}] {property_name}")
        print(f"URLs to check: {len(urls)}")
        print(f"{'='*60}")

        # Track results before this property
        results_before = len(checker.results)

        # Process each URL for this property
        for url in urls:
            checker.base_url = url
            checker.base_domain = urlparse(url).netloc
            checker.crawl_path = checker._extract_crawl_path(url)
            checker.visited_urls = set()  # Reset for each URL
            checker.crawl_website(url, property_name, max_pages=max_pages)

        # Get new results from this property
        new_results = checker.results[results_before:]

        # Update running totals
        checker.properties_processed += 1
        for r in new_results:
            if r['status'] == 'GOOD':
                checker.total_good += 1
            elif r['status'] == 'BAD REDIRECT':
                checker.total_bad += 1
            elif r['status'] == 'ERROR':
                checker.total_errors += 1

        # Append any problems to sheet immediately
        checker._append_to_sheet(new_results)

        # Print running totals
        print(f"  >> Running totals: {checker.properties_processed} properties | GOOD: {checker.total_good} | BAD: {checker.total_bad} | ERRORS: {checker.total_errors} | BLOCKED: {len(checker.manual_review_sites)}")

        # Small delay between properties to avoid rate limits
        time.sleep(1)

    # Add summary and blocked sites at the end
    checker._update_sheet_summary()
    checker.save_results()


def main():
    print("="*60)
    print("REDIRECT CHECKER - TOUR LINK VALIDATOR")
    print("="*60)

    credentials_path = '/Users/lucaswillett/credentials.json'
    output_sheet_id = '18UAf2hhgdS0-tjADyEkRXCPqksGDYPYA67Hd9MYJX1I'

    print("\nModes:")
    print("  1. Single URL (interactive)")
    print("  2. Batch process from Google Sheet")

    mode = input("\nSelect mode (1 or 2): ").strip()

    if mode == '2':
        input_sheet_id = input("Enter input Google Sheet ID (or press Enter for default): ").strip()
        if not input_sheet_id:
            # Default to the sheet the user mentioned
            input_sheet_id = '1zZfUW4qonN21eSo6PeckzweRFlPSHo4CBznGcVpfWtA'

        start_row_input = input("Start from row # (default 1): ").strip()
        start_row = 1
        if start_row_input:
            try:
                start_row = int(start_row_input)
            except:
                pass

        row_limit_input = input("Max properties to process (default all): ").strip()
        row_limit = None
        if row_limit_input:
            try:
                row_limit = int(row_limit_input)
            except:
                pass

        max_pages_input = input("Max pages per URL (default 10): ").strip()
        max_pages = 10
        if max_pages_input:
            try:
                max_pages = int(max_pages_input)
            except:
                pass

        run_batch_mode(credentials_path, input_sheet_id, output_sheet_id, max_pages, start_row, row_limit)
    else:
        run_single_mode(credentials_path, output_sheet_id)

    print("\nDone!")


if __name__ == '__main__':
    main()
