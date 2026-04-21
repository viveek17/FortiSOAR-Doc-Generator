# File: app.py
from flask import Flask, render_template, request, send_file
import os
from generate_docs import generate_pdf_for_web

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    """Serves the homepage UI."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Handles the form submission and generates the PDF."""
    connector_input = request.form.get('connectors')
    
    if not connector_input:
        return "Error: Please enter at least one connector name.", 400
        
    # Split the input by commas and clean it up
    requested_list = [name.strip() for name in connector_input.split(",") if name.strip()]
    
    # Using logger instead of print to avoid Windows OSError
    app.logger.info(f"Received request for: {requested_list}")
    
    # Call your generator script
    pdf_filename = generate_pdf_for_web(requested_list)
    
    if pdf_filename and os.path.exists(pdf_filename):
        # Send the file to the user to download, then clean it up from the server
        response = send_file(pdf_filename, as_attachment=True, download_name="FortiSOAR_Connector_Documentation.pdf")
        return response
    else:
        return "Error: Could not find documentation for those connectors. Please check the spelling.", 500

if __name__ == '__main__':
    # Run the local development server
    app.run(host='0.0.0.0', port=5000, debug=True)