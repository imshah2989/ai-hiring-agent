"""
Google Sheets Exporter for TalentScout.
Exports sourced candidates and AI analysis results to a single Google Sheet.

Setup:
1. Go to https://console.cloud.google.com
2. Enable Google Sheets API + Google Drive API
3. Create a Service Account → download JSON key file
4. Create a Google Sheet → share with the service account email (Editor)
5. Add to .env:
   GOOGLE_SHEETS_CREDENTIALS_FILE=service_account.json
   GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
"""

import os
import json
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

import sys

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except Exception as e:
    GSPREAD_AVAILABLE = False
    print(f"⚠️  gspread not installed. Python: {sys.executable} | Error: {e}")


# Column headers for the single sheet
HEADERS = [
    "Name",
    "Headline",
    "Location",
    "Open to Work",
    "LinkedIn URL",
    "Score",
    "Tier",
    "Recommended Action",
    "Strengths",
    "Gaps",
    "Risk Flags",
    "Reasoning",
    "Role Searched",
    "Search Date",
]


class GoogleSheetsExporter:
    """Exports candidate data to Google Sheets."""

    def __init__(self):
        self.enabled = False
        self.client = None
        self.spreadsheet = None

        if not GSPREAD_AVAILABLE:
            print("⚠️  Google Sheets export disabled (gspread not installed).")
            return

        creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

        if not creds_file or not spreadsheet_id:
            print("⚠️  Google Sheets export disabled (credentials not configured in .env).")
            return

        # Resolve credentials path relative to backend dir
        if not os.path.isabs(creds_file):
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            creds_file = os.path.join(backend_dir, creds_file)

        if not os.path.exists(creds_file):
            print(f"⚠️  Google Sheets credentials file not found: {creds_file}")
            return

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials = Credentials.from_service_account_file(creds_file, scopes=scopes)
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
            self.enabled = True
            print(f"✅ Google Sheets connected: {self.spreadsheet.title}")
        except Exception as e:
            print(f"❌ Google Sheets connection failed: {e}")

    def _get_or_create_worksheet(self, title: str) -> Any:
        """Get existing worksheet or create a new one with headers."""
        try:
            ws = self.spreadsheet.worksheet(title)
            return ws
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=len(HEADERS))
            ws.append_row(HEADERS)
            # Bold the header row
            ws.format("1", {"textFormat": {"bold": True}})
            return ws

    def export_results(
        self,
        sourced_candidates: List[Dict[str, Any]],
        analysis_results: Optional[List[Dict[str, Any]]],
        role: str,
    ):
        """
        Export sourced candidates + analysis results to a single Google Sheet.
        
        - sourced_candidates: list of candidate profile dicts from sourced_candidates.json
        - analysis_results: list of assessment dicts from results.json (can be None if only sourcing done)
        - role: the role searched for
        """
        if not self.enabled:
            print("⚠️  Google Sheets export skipped (not configured).")
            return

        search_date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        # Build a lookup of analysis results by candidate_id
        analysis_lookup = {}
        if analysis_results:
            for result in analysis_results:
                cid = result.get("candidate_id", "")
                analysis_lookup[cid] = result

        # Prepare rows - one per sourced candidate
        rows = []
        for candidate in sourced_candidates:
            profile_url = candidate.get("profile_url", "") or candidate.get("id", "")
            name = candidate.get("name", "Unknown")
            headline = candidate.get("headline", "")
            location = candidate.get("location", "")
            is_otw = "Yes" if candidate.get("is_open_to_work") else "No"

            # Try to match with analysis results
            analysis = analysis_lookup.get(profile_url, {})

            score = analysis.get("overall_score", "")
            tier = analysis.get("tier", "")
            action = analysis.get("recommended_action", "")
            
            rfa = analysis.get("role_fit_analysis", {})
            strengths = ", ".join(rfa.get("strengths", [])) if rfa else ""
            gaps = ", ".join(rfa.get("gaps", [])) if rfa else ""
            risk_flags = ", ".join(analysis.get("risk_flags", [])) if analysis else ""
            reasoning = analysis.get("reasoning_summary", "")

            rows.append([
                name,
                headline[:200] if headline else "",  # Truncate long headlines
                location,
                is_otw,
                profile_url,
                score,
                tier,
                action,
                strengths[:500] if strengths else "",  # Truncate for readability
                gaps[:500] if gaps else "",
                risk_flags,
                reasoning[:500] if reasoning else "",
                role,
                search_date,
            ])

        if not rows:
            print("⚠️  No data to export to Google Sheets.")
            return

        try:
            # Use role + date as the worksheet title
            sheet_title = f"{role[:20]} - {datetime.now(UTC).strftime('%b %d %Y')}"
            ws = self._get_or_create_worksheet(sheet_title)

            # Append all rows at once (efficient batch write)
            ws.append_rows(rows, value_input_option="USER_ENTERED")

            print(f"✅ Exported {len(rows)} candidates to Google Sheet: '{sheet_title}'")
            
        except Exception as e:
            print(f"❌ Google Sheets export error: {e}")
