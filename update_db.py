# File: update_db.py
import requests
import json
import concurrent.futures
import re
import os
from packaging import version

REPO_URL = "https://repo.fortisoar.fortinet.com/connectors/info/"
DB_FILENAME = "connectors_db.json"
LOCAL_MAPPING_FILE = "inspected_elements.json"

def normalize(text):
    """Aggressively removes all non-alphanumeric characters to guarantee a match."""
    if not text: return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def load_local_mapping():
    """Reads the exact URLs from your simple local JSON mapping."""
    mapping = {}
    if not os.path.exists(LOCAL_MAPPING_FILE):
        print(f"[!] Warning: {LOCAL_MAPPING_FILE} not found. Only clean repo URLs will be used.")
        return mapping

    try:
        with open(LOCAL_MAPPING_FILE, 'r', encoding='utf-8') as f:
            raw_urls = json.load(f)
            
        for label, url in raw_urls.items():
            mapping[normalize(label)] = url
    except Exception as e:
        print(f"[!] CRITICAL ERROR loading {LOCAL_MAPPING_FILE}: {e}")
        
    return mapping

def get_connector_folders():
    """Fetches the list of all connector directories from the Fortinet repo."""
    try:
        response = requests.get(REPO_URL, timeout=15)
        response.raise_for_status()
        
        lines = response.text.split('\n')
        folders = [line.split('href="')[1].split('"')[0] for line in lines if 'href="' in line]
        return [f for f in folders if f.endswith('/') and f != '../']
    except Exception as e:
        print(f"[!] Error fetching repository index: {e}")
        return []

def fetch_info_json(folder_name):
    """Downloads the info.json for a specific connector."""
    info_url = f"{REPO_URL}{folder_name}info.json"
    try:
        response = requests.get(info_url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass 
    return None

def build_initial_repo_mapping(folders):
    """PASS 1: Fetch all repo data and isolate the latest version for each connector."""
    repo_db = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_info_json, folders))
        
    for data in results:
        if not data: continue
        
        name = data.get("name")
        ver = data.get("version")
        label = data.get("label")
        help_url = data.get("help_online", "")
        
        if not name or not ver or not label: continue
        
        # If it's a new connector, or if this version is higher than the one we have saved, update it
        if name not in repo_db:
            repo_db[name] = {"version": ver, "label": label, "url": help_url}
        else:
            existing_ver = repo_db[name]["version"]
            try:
                if version.parse(ver) > version.parse(existing_ver):
                    repo_db[name] = {"version": ver, "label": label, "url": help_url}
            except Exception:
                pass
                
    return repo_db

def apply_cybersponse_patch(repo_db, local_mapping):
    """PASS 2: Audit the database for Cybersponse URLs and replace them only if explicitly mapped."""
    final_db = {}
    patched_count = 0
    missing_mappings = 0
    
    for name, data in repo_db.items():
        label = data["label"]
        help_url = data["url"]
        
        # Safety check: convert None to an empty string so .lower() doesn't crash
        if help_url is None:
            help_url = ""
            
        # Check if the URL needs replacing
        if "cybersponse" in help_url.lower():
            norm_label = normalize(label)
            
            if norm_label in local_mapping:
                help_url = local_mapping[norm_label]
                patched_count += 1
            else:
                # NO GUESSING. Just print a warning so the admin knows to update the JSON.
                print(f"  [!] Warning: '{label}' has a legacy cybersponse URL but no local mapping was found. Left unmodified.")
                missing_mappings += 1
                
        # Build the final flat dictionary for the web app
        final_db[name] = {
            "label": label,
            "url": help_url
        }
        
    print(f"\n[*] Successfully patched {patched_count} URLs.")
    if missing_mappings > 0:
        print(f"[*] Left {missing_mappings} legacy URLs unmodified (please add them to your JSON mapping file).")
        
    return final_db

def main():
    print("=== FortiSOAR Connector DB Updater (Strict Mapping Edition) ===")
    
    print("\n[Step 1] Loading local URL mappings...")
    local_mapping = load_local_mapping()
    
    print("\n[Step 2] Fetching repository index...")
    folders = get_connector_folders()
    if not folders:
        print("[!] No folders found. Exiting.")
        return
        
    print(f"\n[Step 3] Parsing info.json files to find the latest versions ({len(folders)} total)...")
    repo_db = build_initial_repo_mapping(folders)
    
    print("\n[Step 4] Auditing URLs and applying patches...")
    final_db = apply_cybersponse_patch(repo_db, local_mapping)
    
    # Sort alphabetically and save
    sorted_db = dict(sorted(final_db.items()))
    with open(DB_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(sorted_db, f, indent=4)
        
    print(f"\n[*] Success! Database saved to {DB_FILENAME} with {len(sorted_db)} unique connectors.")

if __name__ == "__main__":
    main()