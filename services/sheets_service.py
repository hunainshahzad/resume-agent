"""Google Sheets service for URL Sheet (input) and Job Tracker (output)."""

import logging
from datetime import datetime
import gspread

from config import settings

logger = logging.getLogger("resume_agent")


class SheetsService:
    def __init__(self):
        self.gc = gspread.service_account(filename=str(settings.GOOGLE_CREDENTIALS_PATH))
        self.url_sheet = self.gc.open_by_key(settings.URL_SHEET_ID)
        self.tracker_sheet = self.gc.open_by_key(settings.TRACKER_SHEET_ID)

    # --- URL Sheet (read URLs, update status/reason) ---
    # Columns: A=URL, B=Additional Context, C=Status, D=Reason, E=Job Description

    def get_pending_urls(self) -> list[dict]:
        """Read rows where Status is empty or approved from the URL sheet."""
        ws = self.url_sheet.sheet1
        records = ws.get_all_records()
        return [
            {
                "url": r["URL"],
                "additional_context": r.get("Additional Context", ""),
                "row": i + 2,  # +2 for header + 1-index
                "approved": r.get("Status", "").strip().lower() == "approved",
                "job_description": r.get("Job Description", "").strip()
            }
            for i, r in enumerate(records)
            if r.get("Status", "").strip().lower() in ("", "approved")
        ]

    def update_url_status(self, row: int, status: str, reason: str = ""):
        """Update Status and Reason columns in the URL sheet."""
        if row is None:
            return
        ws = self.url_sheet.sheet1
        ws.update(f"C{row}:D{row}", [[status, reason]])

    # --- Job Tracker Sheet (append new completed jobs) ---
    # Columns: Company, Job Title, Location, Status, Date Applied, Resume PDF Path

    def append_to_tracker(self, data: dict):
        """Add a new row to the Job Tracker after successful resume generation."""
        ws = self.tracker_sheet.sheet1
        ws.append_row([
            data["company"],
            data["job_title"],
            data["location"],
            "Resume Generated",
            datetime.now().strftime("%Y-%m-%d"),
            data["pdf_path"]
        ])
