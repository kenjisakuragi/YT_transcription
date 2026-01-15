
import json
import os

def convert():
    raw_path = 'cookies_raw.json'
    out_path = 'note_auth.json'
    
    if not os.path.exists(raw_path):
        print(f"Error: {raw_path} not found.")
        return

    with open(raw_path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    # Playwright expects a dict with "cookies" and "origins"
    storage_state = {
        "cookies": cookies,
        "origins": []
    }
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(storage_state, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully converted {raw_path} to {out_path}")

if __name__ == "__main__":
    convert()
