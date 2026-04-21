# File: update_db.py
import requests
from bs4 import BeautifulSoup
import json
from packaging import version
import concurrent.futures

REPO_URL = "https://repo.fortisoar.fortinet.com/connectors/info/"
DB_FILENAME = "connectors_db.json"

def get_connector_folders():
    print(f"[*] Fetching repository index from {REPO_URL}...")
    try:
        response = requests.get(REPO_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        folders = [link.get('href') for link in soup.find_all('a') 
                   if link.get('href') and link.get('href').endswith('/') and link.get('href') != '../']
        print(f"[*] Found {len(folders)} total connector directories.")
        return folders
    except Exception as e:
        print(f"[!] Error fetching repository index: {e}")
        return []

def fetch_info_json(folder_name):
    info_url = f"{REPO_URL}{folder_name}info.json"
    try:
        response = requests.get(info_url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass 
    return None

def process_single_folder(folder):
    data = fetch_info_json(folder)
    if not data: return None
    name = data.get('name')
    ver = data.get('version', '0.0.0')
    help_url = data.get('help_online')
    label = data.get('label', name.replace('-', ' ').title())
    if not name or not help_url: return None
    return {"name": name, "version": ver, "url": help_url, "label": label}

def build_database():
    folders = get_connector_folders()
    database = {}
    print(f"[*] Processing {len(folders)} connectors using Multi-threading (Hold tight!)...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_single_folder, folders))
        
    for result in results:
        if result:
            name = result["name"]
            ver = result["version"]
            help_url = result["url"]
            label = result["label"]
            
            if name not in database:
                database[name] = {"latest": ver, "label": label, "versions": {ver: help_url}}
            else:
                database[name]["versions"][ver] = help_url
                existing_latest = database[name]["latest"]
                if version.parse(ver) > version.parse(existing_latest):
                    database[name]["latest"] = ver
                    database[name]["label"] = label 
    return database

def main():
    print("=== FortiSOAR Connector DB Updater ===")
    latest_connectors = build_database()
    if not latest_connectors: return
    sorted_db = dict(sorted(latest_connectors.items()))
    with open(DB_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(sorted_db, f, indent=4)
    print(f"\n[SUCCESS] Saved {len(sorted_db)} unique connectors to {DB_FILENAME}!")

if __name__ == "__main__":
    main()