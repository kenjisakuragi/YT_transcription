import argparse
import json
import os
import time
import tempfile
from playwright.sync_api import sync_playwright

def post_note(args):
    """
    Posts a draft article to note.com using data from a JSON file.
    Supports authentication via file (cookies) or persistent profile.
    """
    content_json_path = args.content
    headless = args.headless
    
    # --- Load content ---
    # Handle path vs JSON string
    data = {}
    if isinstance(content_json_path, str) and os.path.exists(content_json_path):
         with open(content_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    elif isinstance(content_json_path, dict):
        data = content_json_path
    else:
        # Check if content is passed as a JSON string
        try:
            data = json.loads(content_json_path)
        except:
            pass # might just be a path that doesn't exist

    # if data is still empty, and path was meant to be a file, warn.
    if not data and not title:
         print(f"Error: Content invalid or file not found: {content_json_path}")
         return

    title = data.get('title', '')
    body = data.get('body', '')
    images = data.get('images', []) 

    if not title:
        print("Error: Title is missing in the content JSON.")
        return

    print("Starting Browser...")
    
    # --- Auth Strategy ---
    # 1. --auth_file argument (Path to auth.json)
    # 2. NOTE_AUTH_JSON environment variable (Content of auth.json)
    # 3. Local chrome_profile directory (Fallback for local dev)
    
    auth_file = args.auth_file if 'auth_file' in args and args.auth_file else None
    auth_json_env = os.environ.get("NOTE_AUTH_JSON")
    
    # Prepare storage_state if available
    storage_state_path = None
    if auth_file and os.path.exists(auth_file):
        print(f"Using auth file: {auth_file}")
        storage_state_path = auth_file
    elif auth_json_env:
        print("Using auth from environment variable.")
        try:
            # Verify JSON first
            json.loads(auth_json_env)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp:
                tmp.write(auth_json_env)
                storage_state_path = tmp.name
        except json.JSONDecodeError:
            print("Warning: NOTE_AUTH_JSON env var is not valid JSON.")

    if storage_state_path:
        print(f"Storage state loaded from: {storage_state_path}")
        user_data_dir = None # Disable persistent context directory if using state file
    else:
        # Fallback to local profile
        user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'chrome_profile')
        user_data_dir = os.path.abspath(user_data_dir)
        print(f"Using local User Data Directory: {user_data_dir}")

    # --- Launch Browser ---
    browser_instance = None
    browser_context = None # To close correctly

    with sync_playwright() as p:
        try:
            if user_data_dir:
                 # Local dev mode with persistent profile
                print("Launching Persistent Context...")
                browser_context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    channel="chrome", 
                    viewport={'width': 1280, 'height': 800}
                )
                page = browser_context.pages[0]
            else:
                # GitHub Actions / Headless with auth state
                print("Launching Browser with Storage State...")
                browser_instance = p.chromium.launch(headless=headless)
                browser_context = browser_instance.new_context(storage_state=storage_state_path, viewport={'width': 1280, 'height': 800})
                page = browser_context.new_page()
                
        except Exception as e:
            print(f"Launch failed ({e}). Retrying with bundled Chromium...")
            if user_data_dir:
                browser_context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    viewport={'width': 1280, 'height': 800}
                )
                page = browser_context.pages[0]
            else:
                browser_instance = p.chromium.launch(headless=headless)
                browser_context = browser_instance.new_context(storage_state=storage_state_path, viewport={'width': 1280, 'height': 800})
                page = browser_context.new_page()

        # --- Automation Logic ---
        print("Navigating to note.com...")
        page.goto("https://note.com/")
        page.wait_for_load_state("networkidle")

        # Check login status
        if page.get_by_text("ログイン", exact=True).is_visible() or page.get_by_text("会員登録", exact=True).is_visible():
            print("Not logged in.")
            if headless:
                 print("Error: Required login in headless mode. Please check your auth.json or secrets.")
                 # Capture screenshot for debug
                 page.screenshot(path="login_failed.png")
                 browser_context.close()
                 if browser_instance: browser_instance.close()
                 return
            else:
                print("PLEASE LOGIN MANUALLY.")
                try:
                    page.wait_for_selector("button:has-text('投稿')", timeout=180000) 
                except:
                    print("Login timeout.")
                    browser_context.close()
                    return
        
        print("Creating new post...")
        # Direct navigation is more robust than clicking
        page.goto("https://note.com/notes/new")
        
        # Wait for editor
        try:
            page.wait_for_selector("textarea[placeholder='記事タイトル']", timeout=15000)
        except:
             print("Editor did not load. Retrying...")
             page.reload()
             page.wait_for_selector("textarea[placeholder='記事タイトル']", timeout=15000)

        # Fill Title
        print(f"Setting Title: {title}")
        page.locator("textarea[placeholder='記事タイトル']").fill(title)
        
        # Fill Body
        print("Setting Body...")
        # Focus editor
        editor_locator = page.locator("div[contenteditable='true']")
        if editor_locator.count() > 0:
            editor_locator.first.click()
            page.keyboard.insert_text(body)
        else:
            page.locator("textarea[placeholder='記事タイトル']").press("Tab")
            page.keyboard.insert_text(body)
        
        # Images (Basic header support if needed, currently skipped for headless simplicity)
        if images:
             print("Note: Image upload skipped in this version.")

        print("Draft content inserted. Waiting for auto-save...")
        time.sleep(5)
        
        print("\nSUCCESS: Draft created.")
        
        if not headless:
            print("Browser open for 10s...")
            time.sleep(10)
            
        if user_data_dir:
             browser_context.close()
        else:
             browser_context.close()
             browser_instance.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a draft on note.com')
    parser.add_argument('--content', required=True, help='Path to JSON file or JSON string containing title, body, and images')
    parser.add_argument('--auth_file', help='Path to auth.json file containing storage state')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    
    args = parser.parse_args()
    
    post_note(args)
