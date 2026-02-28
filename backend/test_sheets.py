import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load env
backend_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path)

# Import exporter (adjust path if needed)
sys.path.append(os.path.join(backend_dir, "src"))
try:
    from google_sheets import GoogleSheetsExporter
    
    print("Connecting to Google Sheets...")
    exporter = GoogleSheetsExporter()
    
    if exporter.enabled:
        print(f"✅ SUCCESS: Connected to '{exporter.spreadsheet.title}'")
        print("Ready for data export.")
    else:
        print("❌ FAILED: Exporter is not enabled. Check .env or credentials.")
except Exception as e:
    print(f"❌ ERROR: {e}")
