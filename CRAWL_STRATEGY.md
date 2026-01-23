# Crawl Strategy & Detection Methods

## Overview

The redirect-checker uses a **two-tier crawl strategy** to comprehensively find virtual tours while remaining efficient. This document explains how the tool discovers tours and detects redirect issues.

## Two-Tier Crawl Strategy

### Tier 1: Shallow Crawl (All Categories)
- **Depth:** 1 page per category
- - **Purpose:** Catch tours that appear on main sections
  - - **Examples:** Homepage, /dining, /experience, /gallery
   
    - This ensures no tours are missed even if they're featured on unexpected pages.
   
    - ### Tier 2: Deep Crawl (Tour-Relevant Categories)
    - - **Depth:** 20 pages per category
      - - **Purpose:** Thoroughly search pages likely to contain tours
        - - **Relevant Keywords:** room, accommodat, stay, guest, suite, meeting, event, wedding, venue, ballroom, experience, gallery, dining, tour
         
          - By combining shallow and deep crawls, the tool achieves:
          - - ✅ **Comprehensive coverage** - Finds tours everywhere
            - - ✅ **Efficiency** - Skips non-relevant pages (blog, news, careers, etc.)
              - - ✅ **Speed** - Intelligent filtering reduces unnecessary crawling
               
                - ## Tour Detection Methods
               
                - The tool detects virtual tours using three different patterns:
               
                - ### Method 1: Direct Links (`<a>` tags)
                - **Pattern:** Traditional hyperlinks to visitingmedia.com
                - **Example:**
                - ```html
                  <a href="https://visitingmedia.com/tt8/?ttid=property-name">Room Tour</a>
                  ```
                  **Detection:** Scans all links for visitingmedia.com URLs
                  **Tool Status:** `type: 'link'`

                  ### Method 2: Data Attributes (`data-link`)
                  **Pattern:** Tour URLs stored in button data attributes (Annapolis Waterfront pattern)
                  **Example:**
                  ```html
                  <button class="view-tour" data-link="https://visitingmedia.com/tt8/?ttid=property-name">
                    <span>HOTEL TOUR</span>
                  </button>
                  ```
                  **Detection:** Parses button elements for `data-link` attributes containing visitingmedia.com URLs
                  **Tool Status:** `type: 'data_link'` or `type: 'button_data_link'`

                  ### Method 3: Dynamic Iframe Injection
                  **Pattern:** JavaScript loads iframes only when user clicks (requires browser automation)
                  **Example:**
                  ```javascript
                  // Click button → JavaScript creates iframe dynamically
                  <iframe src="https://visitingmedia.com/tt8/?ttid=property-name"></iframe>
                  ```
                  **Detection:**
                  - Uses Selenium/Playwright browser automation
                  - - Clicks buttons with 'tour' or 'view' keywords
                    - - Captures dynamically-injected iframes in the DOM
                      - **Tool Status:** `type: 'dynamic_iframe'`
                     
                      - ### Method 4: Static Iframes
                      - **Pattern:** Iframes in the HTML source code
                      - **Example:**
                      - ```html
                        <iframe src="https://visitingmedia.com/tt8/?ttid=property-name"></iframe>
                        ```
                        **Detection:** Parses HTML for iframe elements
                        **Tool Status:** `type: 'iframe'`

                        ## Browser Automation

                        When fewer than 3 tours are found via static parsing, the tool automatically enables **Selenium browser automation** to:
                        - Load JavaScript-heavy pages
                        - - Find dynamically-rendered tour buttons
                          - - Click buttons and capture newly-injected iframes
                            - - Handle modal viewers and popup windows
                             
                              - **Why it matters:** Many modern hotel websites (especially those using certain CMS platforms) render tours dynamically, making static HTML parsing insufficient.
                             
                              - ## Filtering Rules
                             
                              - The tool automatically skips URLs containing these keywords:
                              - - `blog`, `news`, `press`, `career`, `job`, `contact`
                                - - `policy`, `privacy`, `terms`, `sitemap`, `logout`, `login`
                                 
                                  - This prevents wasting time crawling non-tour pages.
                                 
                                  - ## Configuration
                                 
                                  - Users can customize:
                                  - - **max_pages:** Total pages to crawl (default: 30)
                                    -   - With intelligent filtering, ~20 pages covers most properties thoroughly
                                        - - **Browser automation:** Enabled by default for comprehensive detection
                                          -   - Disable for speed (skip dynamic tours)
                                              -   - Enable for completeness (find all tours)
                                               
                                                  - ## Redirect Testing
                                               
                                                  - After finding all tours, the tool tests where each redirect points:
                                                  - - ✅ **GOOD:** Redirects to `/media/` or `/properties/` paths (expected behavior)
                                                    - - ❌ **BAD:** Redirects elsewhere (needs investigation)
                                                     
                                                      - ## Edge Cases & Future Improvements
                                                      - 
                                                      Known patterns not yet handled:
- JavaScript in external files referencing tour IDs
- - API-driven tour loading
  - - Lazy-loaded tours below the fold
    - - Shadow DOM tour containers
      - - Non-visitingmedia.com tour platforms
       
        - These may require additional detection strategies in future versions.
        - 
