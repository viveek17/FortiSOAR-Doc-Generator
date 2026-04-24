# FortiSOAR Connector Documentation Generator

A robust, resilient automation tool designed to scrape, clean, and compile enterprise-grade PDF documentation for FortiSOAR connectors. 

This project bypasses manual documentation hunting by automatically indexing the official Fortinet repository, intelligently extracting specific documentation sections (Prerequisites, Permissions, Configurations) using advanced DOM parsing, and generating a polished PDF with a clickable Table of Contents.

## ✨ Features

* **Automated Database Indexing:** Scans the Fortinet connector repository to dynamically build a flat, versionless database of the absolute latest connector URLs.
* **Resilient Web Scraping:** Utilizes a custom "DOM Climber and Chopper" algorithm via BeautifulSoup to bypass malformed HTML, isolated wrapper `<div>`s, and hidden formatting tags often found in enterprise CMS platforms.
* **WAF Evasion & Throttling:** Built-in headers and randomized request throttling to mimic human navigation and prevent rate-limiting or HTTP 403 blocks.
* **Smart PDF Generation:** Converts raw HTML into a professional PDF using `xhtml2pdf`, featuring a minimalist, dynamically generated, and clickable Table of Contents.
* **Fuzzy Matching:** Users do not need to memorize exact database keys. The tool accepts continuous word fragments (e.g., `Cisco Meraki` instead of `Cisco Meraki MX VPN Firewall`) and perfectly resolves the routing.
* **Web UI & CLI Support:** Run it via the command line or serve it locally using the built-in Flask web application.

## 📂 Project Structure

* `update_db.py` - The chronological database builder. Fetches the latest versions from the repository, applies manual URL patches, and saves the output.
* `generate_docs.py` - The core scraping and PDF generation engine. Contains the DOM traversal logic and the `xhtml2pdf` compiler.
* `app.py` - A lightweight Flask backend that serves the web interface and handles user requests.
* `inspected_elements.json` - A manual override file for patching legacy or broken URLs (e.g., old "cybersponse" links).
* `templates/index.html` - The dark-mode frontend UI for the web application.

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/fortisoar-doc-generator.git](https://github.com/yourusername/fortisoar-doc-generator.git)
   cd fortisoar-doc-generator
   ```

2. **Install dependencies:**
   Ensure you have Python 3.x installed, then install the required packages:
   ```bash
   pip install requests beautifulsoup4 markdown xhtml2pdf Flask packaging
   ```

3. **Configure your overrides (Optional):**
   If you have specific legacy URLs that need manual routing, ensure they are perfectly mapped in `inspected_elements.json`.

## 🛠️ Usage

### Step 1: Build the Database
Before generating any PDFs, you must build the local routing database. This script will fetch the latest versions from Fortinet and apply any necessary patches.
```bash
python update_db.py
```
*Note: You should run this periodically to ensure your local `connectors_db.json` is up to date with the latest Fortinet releases.*

### Step 2: Run the Application
**Via the Web Interface (Recommended):**
Start the Flask server:
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`. Enter the complete names of the connectors you need, separated by commas (e.g., `Exchange, Cisco Meraki MX VPN Firewall, Carbon Black Protect Bit9`), and click Generate.

**Via the Command Line:**
You can bypass the web UI and generate a PDF directly from your terminal:
```bash
python generate_docs.py "Exchange" "Cisco Meraki MX VPN Firewall"
```

## 🧠 How the Scraper Works
Enterprise documentation is rarely formatted consistently. This project implements defensive programming to handle DOM mutations:
1. **The DOM Climber:** If a target header (like `<h2>Prerequisites</h2>`) is isolated inside a formatting container, the script climbs up the DOM tree to find the true parent container before searching for siblings.
2. **The Chopper:** If a "stop header" is hidden deep inside a massive sibling block (like a poorly formatted `<li>`), the script surgically slices the stop header and everything below it out of memory, retaining only the valid content.
3. **The Sanitizer:** Violently removes `<script>`, `<style>`, hidden navigation menus, and honeypot tags before parsing begins.