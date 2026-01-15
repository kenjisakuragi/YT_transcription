from playwright.sync_api import sync_playwright
import time
import os
import json

def get_auth_state(output_path='note_auth.json'):
    """
    Launches a browser for the user to log in to note.com,
    then saves the storage state (cookies, local storage) to a JSON file.
    """
    print("Launching browser for login...")
    with sync_playwright() as p:
        # Launch non-headless so user can log in
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://note.com/login")
        
        print("\n" + "="*60)
        print("PLEASE LOG IN TO NOTE.COM IN THE BROWSER WINDOW.")
        print("Once you are successfully logged in (and see your dashboard/icon),")
        print("press Enter in this terminal to save the authentication state.")
        print("="*60 + "\n")
        
        # Wait for user input
        input("Press Enter after you have logged in...")
        
        # Save state
        context.storage_state(path=output_path)
        print(f"Authentication state saved to: {os.path.abspath(output_path)}")
        
        # Verify by printing cookie names (optional safety check)
        cookies = context.cookies()
        print(f"Captured {len(cookies)} cookies.")
        
        browser.close()

if __name__ == "__main__":
    get_auth_state()
