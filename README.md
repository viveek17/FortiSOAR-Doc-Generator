# FortiSOAR Integration Pre-requisite Generator

A Python-based automation tool designed for SecOps workflows. This tool fetches FortiSOAR connector metadata directly from the official Fortinet repository and generates unified, professionally formatted PDF documentation covering integration prerequisites, permissions, and configurations.

## 🚀 Features

* **Automated Data Scraping:** Includes a multi-threaded web scraper (`update_db.py`) that continuously pulls the latest connector information and versions from the FortiSOAR repository.
* **Smart Content Parsing:** Intelligently extracts specific HTML sections from standard documentation and GitHub markdown files to isolate exact prerequisite data.
* **Modern Web Interface:** A sleek, dark-mode Flask UI (`app.py`) built for security professionals, allowing users to request documentation for multiple connectors simultaneously.
* **Granular Version Control:** Supports fetching documentation for specific connector versions using the `connector_name:version` syntax (e.g., `zscaler:2.1.0`).
* **Professional PDF Engine:** Utilizes `xhtml2pdf` to render clean, readable technical documentation with zebra-striped tables and formatted code blocks.

## 📁 Repository Structure

```text
FortiSOAR-Doc-Generator/
├── app.py                   # Flask Web Server (Main Entry Point)
├── generate_docs.py         # Core Logic: Scraping & PDF Generation
├── update_db.py             # Utility: Multi-threaded scraper to refresh the local DB
├── requirements.txt         # Python dependencies
├── .gitignore               # Git ignore rules
└── templates/               
    └── index.html           # Dark Mode Web UI

🛠️ Installation & Setup
Clone the repository:

Bash
git clone [https://github.com/your-username/FortiSOAR-Doc-Generator.git](https://github.com/your-username/FortiSOAR-Doc-Generator.git)
cd FortiSOAR-Doc-Generator
Install dependencies:
Ensure you have Python 3.x installed, then run:

Bash
pip install -r requirements.txt
Initialize the Database:
Run the updater script to fetch all current connector metadata locally. This creates the connectors_db.json file.

Bash
python update_db.py
Run the Application:
Start the Flask server:

Bash
python app.py
Access the web interface at http://127.0.0.1:5000

💻 Usage
In the web interface, you can request documentation for multiple connectors by entering their names separated by commas.

Examples:

Latest versions: fortigate, virus-total, crowdstrike

Specific versions: zscaler:2.1.0, active-directory:2.4.0

The tool will parse the documentation in real-time and generate a combined PDF for download.

👨‍💻 Author
Vivek Ingle

Security Orchestration, Automation, and Response (SOAR) Engineer

Specializing in SecOps Automation, Python, and API Integrations.