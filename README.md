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


## Features

- **Multi-Method Detection**: Detects virtual tours using 4 different methods:
-   - Static direct links (href attributes)
    -   - Data attribute links (data-link attributes)
        -   - Dynamic JavaScript-rendered modals and iframes
            -   - Static iframe embeds
             
                - - **Two-Tier Crawl Strategy**: Intelligently crawls websites without wasting time on irrelevant pages:
                  -   - **Tier 1 (Shallow)**: Crawls 1 page from each category to catch featured tours
                      -   - **Tier 2 (Deep)**: Crawls up to 20 pages of tour-relevant categories only
                       
                          - - **Browser Automation**: Uses Selenium WebDriver for JavaScript-heavy sites where tours are dynamically loaded
                           
                            - - **Google Sheets Integration**: Automatically exports results to a Google Sheets spreadsheet for analysis and reporting
                             
                              - - **Comprehensive Coverage**: Tours can appear on homepages, dining pages, visitor information sections - not just obvious locations
                               
                                - ## Crawl Strategy Details
                               
                                - See [CRAWL_STRATEGY.md](./CRAWL_STRATEGY.md) for detailed information about how the tool intelligently crawls websites while avoiding irrelevant pages like blogs, press releases, and career pages.
                               
                                - ## Advanced Configuration
                               
                                - The tool automatically:
                                - - Enables browser automation by default for JavaScript-heavy sites
                                  - - Filters out URLs containing: blog, news, press, career, job, contact, policy, privacy, terms, sitemap, logout, login
                                    - - Tests redirects to determine if they're GOOD (go to /media/ or /properties/) or BAD (go elsewhere)
                                      - - Captures tour location (which page/section) and redirect destination for complete audit trail
