# Setup Guide

## Step 1: Install Python & Requirements

Make sure you have Python 3.9+ installed:

```bash
python3 --version
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Step 2: Create Google Cloud Project & Get Credentials

This tool writes results to Google Sheets using the Google Sheets API.

### A. Create a Google Cloud Project

1. Go to Google Cloud Console
2. 2. Click "Select a Project" at the top
   3. 3. Click "NEW PROJECT"
      4. 4. Name it "Redirect Checker" and click Create
         5. 5. Wait for project to be created
           
            6. ### B. Enable Google Sheets API
           
            7. 1. In Google Cloud Console, go to "APIs & Services" → "Library"
               2. 2. Search for "Google Sheets API"
                  3. 3. Click it and press "ENABLE"
                     4. 4. Also enable "Google Drive API"
                       
                        5. ### C. Create Service Account
                       
                        6. 1. Go to "APIs & Services" → "Credentials"
                           2. 2. Click "Create Credentials" → "Service Account"
                              3. 3. Fill in:
                                 4.    - Service account name: redirect-checker
                                       -    - Description: "Virtual tour redirect checker"
                                            - 4. Click "Create and Continue"
                                              5. 5. Grant role: Editor
                                                 6. 6. Click "Continue" then "Done"
                                                   
                                                    7. ### D. Create & Download JSON Key
                                                   
                                                    8. 1. Click the service account you just created
                                                       2. 2. Go to "Keys" tab
                                                          3. 3. Click "Add Key" → "Create new key"
                                                             4. 4. Choose "JSON" format
                                                                5. 5. Click "Create"
                                                                   6. 6. The JSON file downloads automatically
                                                                      7. 7. Rename it to credentials.json
                                                                         8. 8. Move to your project folder
                                                                           
                                                                            9. ### E. Share Google Sheet with Service Account
                                                                           
                                                                            10. 1. Open your Google Sheet
                                                                                2. 2. Open credentials.json in text editor
                                                                                   3. 3. Find the "client_email" field and copy it
                                                                                      4. 4. Click Share in your Google Sheet
                                                                                         5. 5. Paste that email and give it "Editor" access
                                                                                           
                                                                                            6. ### F. Update Script with Sheet ID
                                                                                           
                                                                                            7. 1. Open your Google Sheet in browser
                                                                                               2. 2. Copy the ID from the URL: https://docs.google.com/spreadsheets/d/COPY-THIS-PART/edit
                                                                                                  3. 3. In redirect_checker.py, find:
                                                                                                     4.    ```python
                                                                                                              sheet_id = '18UAf2hhgdS0-tjADyEkRXCPqksGDYPYA67Hd9MYJX1I'
                                                                                                              ```
                                                                                                           4. Replace with your ID:
                                                                                                           5.    ```python
                                                                                                                    sheet_id = 'YOUR-SHEET-ID-HERE'
                                                                                                                    ```
                                                                                                                 
                                                                                                                 ## Step 3: Test It Works
                                                                                                             
                                                                                                             Run the script:
                                                                                                       
                                                                                                       ```bash
                                                                                                       python3 redirect_checker.py
                                                                                                       ```
                                                                                                       
                                                                                                       You should be prompted for property URL and name.
                                                                                                     
                                                                                                     ## Troubleshooting
                                                                                                     
                                                                                                     - "ModuleNotFoundError": Run `pip install -r requirements.txt`
                                                                                                     - - "Could not connect to Google Sheets": Check credentials.json path is correct
                                                                                                       - - "No tour links found": Check URL ends with trailing slash
