"""
HeyReach → Google Sheets webhook.

Deploy: modal deploy execution/heyreach_webhook.py
Test:   curl -X POST https://YOUR-URL/heyreach-reply -H "Content-Type: application/json" -d '{"test": true}'

When someone replies in HeyReach, this webhook:
1. Receives the payload
2. Appends a row to Google Sheets with lead info
3. You manually manage follow-up status in the sheet
"""

import modal
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heyreach-webhook")

app = modal.App("heyreach-crm")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("gspread", "google-auth")
)

# Google Sheets config - UPDATE THIS with your sheet ID
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"  # TODO: Replace with actual sheet ID
SHEET_NAME = "Replies"


def get_gspread_client():
    """Initialize gspread with service account."""
    import gspread
    from google.oauth2.service_account import Credentials
    import os

    # Load credentials from Modal secret
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not set in Modal secrets")

    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("google-service-account")],
)
@modal.web_endpoint(method="POST")
def heyreach_reply(data: dict):
    """
    Webhook endpoint for HeyReach reply events.

    HeyReach webhook payload (expected fields):
    - leadFirstName, leadLastName
    - leadLinkedInUrl
    - leadCompany
    - leadPosition
    - messageContent (the reply text)
    - campaignName
    - timestamp

    Adjust field names based on actual HeyReach payload.
    """
    logger.info(f"Received webhook: {json.dumps(data, indent=2)}")

    try:
        # Extract fields from HeyReach payload
        # NOTE: Adjust these field names based on actual HeyReach webhook format
        first_name = data.get("leadFirstName") or data.get("firstName") or data.get("lead_first_name") or ""
        last_name = data.get("leadLastName") or data.get("lastName") or data.get("lead_last_name") or ""
        linkedin_url = data.get("leadLinkedInUrl") or data.get("linkedinUrl") or data.get("lead_linkedin_url") or ""
        company = data.get("leadCompany") or data.get("company") or data.get("lead_company_name") or ""
        position = data.get("leadPosition") or data.get("position") or data.get("lead_position") or ""
        message = data.get("messageContent") or data.get("message") or data.get("reply_content") or ""
        campaign = data.get("campaignName") or data.get("campaign") or ""

        # Timestamp
        received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build row for sheet
        row = [
            received_at,
            f"{first_name} {last_name}".strip(),
            linkedin_url,
            company,
            position,
            campaign,
            message[:500] if message else "",  # Truncate long messages
            "New",  # Status column - you update this manually
            ""      # Notes column
        ]

        # Append to Google Sheet
        gc = get_gspread_client()
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        sheet.append_row(row, value_input_option="USER_ENTERED")

        logger.info(f"Added to sheet: {first_name} {last_name}")

        return {
            "status": "success",
            "message": f"Added {first_name} {last_name} to CRM",
            "received_at": received_at
        }

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Still return 200 so HeyReach doesn't retry
        return {
            "status": "error",
            "message": str(e),
            "raw_data": data  # Log raw data for debugging
        }


@app.function(image=image)
@modal.web_endpoint(method="GET")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "heyreach-crm"}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("google-service-account")],
)
@modal.web_endpoint(method="POST")
def test_sheet(data: dict):
    """Test endpoint to verify Google Sheets connection."""
    try:
        gc = get_gspread_client()
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # Add a test row
        test_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Test Lead",
            "https://linkedin.com/in/test",
            "Test Company",
            "Test Position",
            "Test Campaign",
            "This is a test message",
            "New",
            "Test row - can delete"
        ]
        sheet.append_row(test_row, value_input_option="USER_ENTERED")

        return {"status": "success", "message": "Test row added to sheet"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
