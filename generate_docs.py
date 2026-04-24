# File: generate_docs.py
import requests
import markdown
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from xhtml2pdf import pisa
import json
import os
import argparse
import re 
import time
import random

DB_FILENAME = "connectors_db.json"

def normalize_name(name):
    """Strips spaces, hyphens, and underscores to allow fuzzy matching."""
    return re.sub(r'[\s\-_]', '', name).lower()

def get_raw_github_url(url):
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def extract_section(soup, base_url, start_titles, stop_titles):
    """Finds a specific header by title and intelligently extracts all HTML elements."""
    for title in start_titles:
        headers = soup.find_all(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and title.lower() in tag.text.lower())
        
        for header in headers:
            content_html = ""
            target = header
            curr = target.find_next_sibling()
            
            # The DOM Climber
            while not curr and target.parent and target.parent.name not in ['body', 'html']:
                target = target.parent
                curr = target.find_next_sibling()
                
            while curr:
                # 1. Stop if the current sibling is a stop header
                if curr.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                    if any(stop.lower() in curr.text.lower() for stop in stop_titles):
                        break
                        
                # 2. Stop if a stop header is hidden INSIDE this sibling block
                stop_found = False
                if hasattr(curr, 'find'):
                    nested_stop = None
                    for stop in stop_titles:
                        nested_stop = curr.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'h5'] and stop.lower() in tag.text.lower())
                        if nested_stop:
                            stop_found = True
                            break
                    
                    if stop_found and nested_stop:
                        # THE CHOPPER
                        for sibling in list(nested_stop.find_next_siblings()):
                            sibling.extract()
                        nested_stop.extract()
                        content_html += str(curr)
                        break
                        
                # Fix relative image links
                if hasattr(curr, 'find_all'):
                    for img in curr.find_all('img'):
                        if img.get('src') and not img['src'].startswith('http'):
                            img['src'] = urljoin(base_url, img['src'])
                            img['style'] = "max-width: 500px;" 
                            
                content_html += str(curr)
                curr = curr.find_next_sibling()
                
            # GHOST TAG DETECTOR
            temp_soup = BeautifulSoup(content_html, 'html.parser')
            if temp_soup.get_text(strip=True) or temp_soup.find('img'):
                return content_html
                
    return "" # Return empty if section is not found

def fetch_github_markdown(github_url):
    raw_url = get_raw_github_url(github_url)
    response = requests.get(raw_url, timeout=15)
    response.raise_for_status()
    html_string = markdown.markdown(response.text, extensions=['tables'])
    return BeautifulSoup(html_string, 'html.parser')

def process_url(url, index, total_count, connector_name, unique_id):
    """Processes the URL and injects the unique_id into the header for the Table of Contents."""
    safe_url = url.encode('ascii', 'ignore').decode('ascii')
    print(f"[{index}/{total_count}] Fetching: {safe_url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        actual_parsed_url = url
        
        if "github.com" in url:
            soup = fetch_github_markdown(url)
        else:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
                    response.raise_for_status()
                    break 
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"  -> Connection dropped by server. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        raise e 

            actual_parsed_url = response.url 
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # THE DOM SANITIZER
            for unwanted in soup(['script', 'style', 'nav', 'footer', 'aside', 'noscript']):
                unwanted.extract()
            for hidden in soup.find_all(class_=re.compile(r'sr-only|hidden|invisible')):
                hidden.extract()
            
            gh_link = soup.find('a', href=lambda href: href and "github.com/fortinet-fortisoar" in href)
            if gh_link:
                redirect_url = gh_link['href']
                print(f"  -> Detected GitHub Redirect! Hopping to: {redirect_url}")
                soup = fetch_github_markdown(redirect_url)
                actual_parsed_url = redirect_url 
        
        prereq_stops = ["Minimum Permissions", "Configuring the connector", "Configuration parameters", "Actions supported"]
        perm_stops = ["Configuring the connector", "Configuration parameters", "Actions supported"]
        config_stops = ["Actions supported", "Included playbooks", "Data Ingestion"]

        prereqs = extract_section(soup, actual_parsed_url, ["Prerequisites to configuring", "Prerequisites"], prereq_stops)
        permissions = extract_section(soup, actual_parsed_url, ["Minimum Permissions Required", "Permissions"], perm_stops)
        config = extract_section(soup, actual_parsed_url, ["Configuration parameters", "Configuring the connector"], config_stops)
        
        # --- THE DYNAMIC HTML BUILDER WITH ANCHOR ID ---
        html_content = f"""
        <div class="connector-block">
            <h1 class="connector-title" id="{unique_id}"><a name="{unique_id}"></a>{index}. {connector_name}</h1>
            <p class="source-link">Source: <a href="{actual_parsed_url}">{actual_parsed_url}</a></p>
        """
        
        if prereqs:
            html_content += f"<h2>Prerequisites to configuring the connector</h2>\n{prereqs}\n"
            
        if permissions:
            html_content += f"<h2>Minimum Permissions Required</h2>\n{permissions}\n"
            
        if config:
            html_content += f"<h2>Configuration parameters</h2>\n{config}\n"
            
        html_content += "</div>\n"
        
        if index < total_count: html_content += "<pdf:nextpage />"
        return html_content
        
    except Exception as e:
        safe_error = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"  -> Error processing {safe_url}: {safe_error}")
        return f'<div class="connector-block"><h1 class="connector-title" style="color: red;" id="{unique_id}"><a name="{unique_id}"></a>{index}. Error</h1><p>{safe_error}</p></div>'

def convert_html_to_pdf(source_html, output_filename):
    with open(output_filename, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(source_html, dest=result_file)
    return pisa_status.err

def load_database():
    if not os.path.exists(DB_FILENAME):
        print(f"[!] Database '{DB_FILENAME}' not found. Please run update_db.py first.")
        return None
    with open(DB_FILENAME, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Generate FortiSOAR Pre-requisites PDF.")
    parser.add_argument("connectors", nargs="*", help="List of connector names (wrap multi-word names in quotes)")
    parser.add_argument("-f", "--file", help="Path to a text file containing connector names (one per line)")
    args = parser.parse_args()

    requested_connectors = []

    if args.file:
        if os.path.exists(args.file):
            with open(args.file, 'r', encoding='utf-8') as f:
                requested_connectors = [line.strip() for line in f if line.strip()]
        else:
            print(f"[!] File not found: {args.file}")
            return
    elif args.connectors:
        requested_connectors = args.connectors
    else:
        print("Enter connector names separated by COMMAS.")
        print("(Warning: Do not paste a multi-line vertical list here, it will only read the first line!)")
        user_input = input("> ")
        requested_connectors = [name.strip() for name in user_input.split(",") if name.strip()]

    if not requested_connectors: 
        print("[!] No connectors provided to process.")
        return
        
    generate_pdf_for_web(requested_connectors)

def generate_pdf_for_web(requested_connectors):
    db = load_database()
    if not db: return None

    items_to_process = []
    
    for requested_item in requested_connectors:
        search_name = requested_item.split(":")[0].strip()
        normalized_search = normalize_name(search_name)
        found = False
        
        for db_name, data in db.items():
            if normalized_search in normalize_name(db_name) or normalized_search in normalize_name(data.get('label', '')):
                display_name = data.get('label', db_name.replace('-', ' ').title())
                target_url = data['url']
                items_to_process.append((display_name, target_url))
                found = True
                break 
                
        if not found:
            print(f"[!] Could not find connector: {requested_item}")

    if not items_to_process: return None

    # --- 1. PRE-BUILD THE INDEX TABLE ---
    index_rows = ""
    items_with_ids = []
    
    for i, (name, url) in enumerate(items_to_process, start=1):
        # Create a safe, unique anchor ID for each connector
        unique_id = f"connector_anchor_{i}"
        items_with_ids.append((name, url, unique_id))
        
        # FIXED: This line is now correctly indented INSIDE the loop
        index_rows += f'<tr><td class="index-col-left"><a href="#{unique_id}" class="index-link">{name}</a></td><td class="index-col-right"><pdf:pagenumber refid="{unique_id}" /></td></tr>\n'
    
    # --- 2. BUILD THE FIRST PAGE (TITLE AND INDEX ONLY) ---
    # FIXED: h1.main-title is now set to text-align: center;
    combined_html = f"""
    <html>
    <head>
        <style>
            @page {{ size: a4 portrait; margin: 2cm; @frame footer {{ -pdf-frame-content: footerContent; bottom: 1cm; margin-left: 2cm; margin-right: 2cm; height: 1cm; }} }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.6; color: #333333; }}
            h1.main-title {{ font-size: 20pt; font-weight: bold; color: #000000; padding-bottom: 8px; margin-bottom: 25px; text-align: center; }}
            h1.connector-title {{ font-size: 18pt; font-weight: bold; margin-top: 10px; margin-bottom: 8px; color: #2980b9; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
            h2 {{ font-size: 14pt; font-weight: bold; margin-top: 18px; margin-bottom: 10px; color: #2c3e50; }}
            h3 {{ font-size: 12pt; font-weight: bold; margin-top: 15px; margin-bottom: 8px; color: #34495e; }}
            .source-link {{ font-size: 9pt; color: #7f8c8d; margin-top: 0; margin-bottom: 20px; font-style: italic; }}
            a {{ color: #2980b9; text-decoration: none; }}
            
            /* General Tables */
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 20px; page-break-inside: avoid; }}
            th, td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; vertical-align: top; }}
            th {{ background-color: #ecf0f1; font-weight: bold; color: #2c3e50; -pdf-keep-with-next: true; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            
            /* Index Table Styling */
            table.index-table {{ width: 100%; border: none; margin-top: 10px; }}
            table.index-table td {{ border: none; padding: 8px 5px; font-size: 12pt; color: #000000; }}
            table.index-table tr:nth-child(even) {{ background-color: transparent; }}
            td.index-col-left {{ font-weight: bold; width: 90%; }}
            td.index-col-right {{ text-align: left; font-weight: bold; width: 10%; }}
            
            /* Hyperlink Styling for Index to match standard text */
            a.index-link {{ color: #000000; text-decoration: none; }}
            
            ul, ol {{ margin-top: 8px; margin-bottom: 15px; padding-left: 25px; page-break-inside: avoid;}}
            li {{ margin-bottom: 6px; }}
            p {{ margin-bottom: 10px; margin-top: 5px; }}
            img {{ max-width: 500px; margin: 15px 0; border: 1px solid #dcdde1; }}
            code, pre {{ font-family: "Courier New", Courier, monospace; background-color: #f1f2f6; padding: 2px 4px; border: 1px solid #dfe4ea; border-radius: 3px; font-size: 9pt; color: #c0392b; }}
            pre {{ padding: 10px; display: block; white-space: pre-wrap; color: #2f3640; border-left: 3px solid #2980b9; }}
        </style>
    </head>
    <body>
        <div id="footerContent" style="text-align: right; font-size: 9pt; color: #555;">Page <pdf:pagenumber></div>
        
        <h1 class="main-title">FortiSOAR Integrations Pre-requisites</h1>
        
        <table class="index-table">
            {index_rows}
        </table>
        
        <pdf:nextpage />
    """

    # --- 3. BUILD THE CONNECTOR PAGES ---
    total_items = len(items_with_ids)
    for i, (name, url, unique_id) in enumerate(items_with_ids, start=1):
        combined_html += process_url(url, i, total_items, name, unique_id)
        
        if i < total_items:
            delay = random.uniform(1.5, 3.5)
            print(f"  [+] Sleeping for {delay:.2f} seconds to prevent rate limiting...")
            time.sleep(delay)
            
    combined_html += "</body></html>"
    
    output_filename = f"Connector_Docs_{int(time.time())}.pdf"
    error = convert_html_to_pdf(combined_html, output_filename)
    
    if not error: return output_filename
    return None

if __name__ == "__main__":
    main()