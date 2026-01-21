# Redirect Checker - Virtual Tour Automation

A Python tool that crawls hotel/property websites and identifies broken virtual tour redirects.

## What It Does

- Crawls property websites looking for visitingmedia.com virtual tour iframes
- - Tests each tour link to see where it redirects
  - - Marks redirects as GOOD (goes to /media/) or BAD (goes elsewhere)
    - - Exports results to Google Sheets for easy analysis
     
      - ## Setup
     
      - 1. Install Python requirements: `pip install -r requirements.txt`
        2. 2. Follow SETUP.md for Google Cloud credentials
           3. 3. Update sheet_id in redirect_checker.py
              4. 4. Run: `python3 redirect_checker.py`
                
                 5. ## Usage
                
                 6. ```bash
                    python3 redirect_checker.py
                    ```

                    Enter property URL, name, and max pages to crawl.

                    ## Output

                    Results export to Google Sheets with columns:
                    - Website Name
                    - - Original URL (visitingmedia.com link)
                      - - Page Found On (which room/page has the tour)
                        - - Redirects To (where it actually goes)
                          - - Status (GOOD or BAD)
                            - - Timestamp
