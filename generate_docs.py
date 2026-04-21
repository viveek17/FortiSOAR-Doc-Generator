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

DB_FILENAME = "connectors_db.json"

def normalize_name(name):
    """Strips spaces, hyphens, and underscores to allow fuzzy matching."""
    return re.sub(r'[\s\-_]', '', name).lower()

def get_raw_github_url(url):
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def extract_section(soup, base_url, start_titles, stop_titles):
    """Finds a specific header by title and extracts all HTML elements."""
    for title in start_titles:
        header = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and title.lower() in tag.text.lower())
        if header:
            content_html = ""
            curr = header.find_next_sibling()
            while curr:
                if curr.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                    if any(stop.lower() in curr.text.lower() for stop in stop_titles):
                        break 
                if hasattr(curr, 'find_all'):
                    for img in curr.find_all('img'):
                        if img.get('src') and not img['src'].startswith('http'):
                            img['src'] = urljoin(base_url, img['src'])
                            img['style'] = "max-width: 500px;" 
                content_html += str(curr)
                curr = curr.find_next_sibling()
            return content_html
    return "<p><em>Section not found in documentation.</em></p>"

def fetch_github_markdown(github_url):
    raw_url = get_raw_github_url(github_url)
    response = requests.get(raw_url, timeout=15)
    response.raise_for_status()
    html_string = markdown.markdown(response.text, extensions=['tables'])
    return BeautifulSoup(html_string, 'html.parser')

def process_url(url, index, total_count, connector_name):
    safe_url = url.encode('ascii', 'ignore').decode('ascii')
    print(f"[{index}/{total_count}] Fetching: {safe_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        actual_parsed_url = url
        if "github.com" in url:
            soup = fetch_github_markdown(url)
        else:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
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
        
        html_content = f"""
        <div class="connector-block">
            <h1 class="connector-title">{index}. {connector_name}</h1>
            <p class="source-link">Source: <a href="{actual_parsed_url}">{actual_parsed_url}</a></p>
            <h2>Prerequisites to configuring the connector</h2>
            {prereqs}
            <h2>Minimum Permissions Required</h2>
            {permissions}
            <h2>Configuration parameters</h2>
            {config}
        </div>
        """
        if index < total_count: html_content += "<pdf:nextpage />"
        return html_content
    except Exception as e:
        safe_error = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"  -> Error processing {safe_url}: {safe_error}")
        return f'<div class="connector-block"><h1 class="connector-title" style="color: red;">{index}. Error</h1><p>{safe_error}</p></div>'

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
    parser.add_argument("connectors", nargs="*", help="List of connector names")
    args = parser.parse_args()

    if args.connectors:
        requested_connectors = args.connectors
    else:
        user_input = input("Enter connector names (separated by commas): ")
        requested_connectors = [name.strip() for name in user_input.split(",") if name.strip()]

    if not requested_connectors: return
    generate_pdf_for_web(requested_connectors) # CLI delegates to the same logic

def generate_pdf_for_web(requested_connectors):
    """Wrapper function to allow Flask to call the generator."""
    db = load_database()
    if not db: return None

    items_to_process = []
    
    for requested_item in requested_connectors:
        requested_version = None
        if ":" in requested_item:
            parts = requested_item.split(":", 1)
            search_name = parts[0].strip()
            requested_version = parts[1].strip()
        else:
            search_name = requested_item.strip()

        normalized_search = normalize_name(search_name)
        found = False
        
        for db_name, data in db.items():
            if normalized_search in normalize_name(db_name):
                display_name = data.get('label', db_name.replace('-', ' ').title())
                if requested_version and requested_version in data['versions']:
                    target_url = data['versions'][requested_version]
                    display_name += f" (v{requested_version})"
                    items_to_process.append((display_name, target_url))
                else:
                    target_ver = data['latest']
                    target_url = data['versions'][target_ver]
                    items_to_process.append((display_name, target_url))
                found = True
                break 
                
    if not items_to_process: return None

    combined_html = """
    <html>
    <head>
        <style>
            @page { size: a4 portrait; margin: 2cm; @frame footer { -pdf-frame-content: footerContent; bottom: 1cm; margin-left: 2cm; margin-right: 2cm; height: 1cm; } }
            body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.6; color: #333333; }
            h1.main-title { font-size: 24pt; font-weight: bold; color: #1a252f; border-bottom: 2px solid #2c3e50; padding-bottom: 8px; margin-bottom: 25px; text-align: center; }
            h1.connector-title { font-size: 18pt; font-weight: bold; margin-top: 10px; margin-bottom: 8px; color: #2980b9; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
            h2 { font-size: 14pt; font-weight: bold; margin-top: 18px; margin-bottom: 10px; color: #2c3e50; }
            h3 { font-size: 12pt; font-weight: bold; margin-top: 15px; margin-bottom: 8px; color: #34495e; }
            h4, h5 { font-size: 11pt; font-weight: bold; margin-top: 12px; margin-bottom: 6px; color: #7f8c8d; font-style: italic; }
            .source-link { font-size: 9pt; color: #7f8c8d; margin-top: 0; margin-bottom: 20px; font-style: italic; }
            a { color: #2980b9; text-decoration: none; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 20px; page-break-inside: avoid; }
            th, td { border: 1px solid #bdc3c7; padding: 8px; text-align: left; vertical-align: top; }
            th { background-color: #ecf0f1; font-weight: bold; color: #2c3e50; -pdf-keep-with-next: true; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            ul, ol { margin-top: 8px; margin-bottom: 15px; padding-left: 25px; page-break-inside: avoid;}
            li { margin-bottom: 6px; }
            p { margin-bottom: 10px; margin-top: 5px; }
            img { max-width: 500px; margin: 15px 0; border: 1px solid #dcdde1; }
            code, pre { font-family: "Courier New", Courier, monospace; background-color: #f1f2f6; padding: 2px 4px; border: 1px solid #dfe4ea; border-radius: 3px; font-size: 9pt; color: #c0392b; }
            pre { padding: 10px; display: block; white-space: pre-wrap; color: #2f3640; border-left: 3px solid #2980b9; }
        </style>
    </head>
    <body>
        <div id="footerContent" style="text-align: right; font-size: 9pt; color: #555;">Page <pdf:pagenumber></div>
        <h1 class="main-title">Integrations Pre-requisites</h1>
    """

    total_items = len(items_to_process)
    for i, (name, url) in enumerate(items_to_process, start=1):
        combined_html += process_url(url, i, total_items, name)
        
    combined_html += "</body></html>"
    
    output_filename = f"Connector_Docs_{int(time.time())}.pdf"
    error = convert_html_to_pdf(combined_html, output_filename)
    
    if not error: return output_filename
    return None

if __name__ == "__main__":
    main()