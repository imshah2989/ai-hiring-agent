import os
import json
import time
from google.oauth2 import service_account
from google.auth.transport.requests import Request

def diagnose_auth():
    creds_file = "service_account.json"
    if not os.path.exists(creds_file):
        print(f"❌ Error: {creds_file} not found in current directory.")
        return

    with open(creds_file, "r") as f:
        data = json.load(f)
        email = data.get("client_email")
        project_id = data.get("project_id")
        print(f"--- Credentials Info ---")
        print(f"Client Email: {email}")
        print(f"Project ID: {project_id}")
        print(f"Private Key ID: {data.get('private_key_id')}")
        print(f"------------------------")

    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        print("\nAttempting to generate and refresh token...")
        credentials = service_account.Credentials.from_service_account_file(creds_file, scopes=scopes)
        credentials.refresh(Request())
        print("✅ Success! Token obtained.")
        print(f"Token expiry: {credentials.expiry}")
    except Exception as e:
        print(f"\n❌ Auth Failure: {e}")
        if "account not found" in str(e).lower():
            print("\n💡 POSSIBLE CAUSES:")
            print("1. The Service Account was DELETED in Google Cloud Console.")
            print("2. The Project ID is incorrect or the project was deleted.")
            print("3. There is a typo in the client_email inside the JSON.")
            print("\nACTION REQUIRED: Please go to Google Cloud Console and verify that the service")
            print(f"account '{email}' still exists in project '{project_id}'.")

if __name__ == "__main__":
    diagnose_auth()
