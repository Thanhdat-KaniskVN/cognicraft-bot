# test_gcal.py - Test GCal event with reminders
import sys, os
sys.path.insert(0, os.getcwd())

from pathlib import Path
from datetime import datetime, timedelta
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TZ = pytz.timezone("Asia/Ho_Chi_Minh")

CREDS = "switch/credentials.json"
TOKEN = "switch/token.json"
CAL_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")

print("=" * 60)
print("GCAL TEST - event with reminders 30/15/5")
print("=" * 60)
print(f"Credentials: {CREDS}")
print(f"Token:       {TOKEN}")
print(f"Calendar ID: {CAL_ID}")
print()

# Auth
creds = None
if Path(TOKEN).exists():
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    print(f"[Auth] Loaded token, valid={creds.valid}")

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        print("[Auth] Token refreshed")
    else:
        if not Path(CREDS).exists():
            print(f"[ERR] {CREDS} not found")
            sys.exit(1)
        flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
        creds = flow.run_local_server(port=0)
        print("[Auth] New token created")
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())

service = build("calendar", "v3", credentials=creds)
print("[Auth] Service built\n")

# Build event with reminders
now = datetime.now(TZ)
start = now + timedelta(minutes=20)
end = start + timedelta(minutes=60)

event = {
    "summary": "[TEST] Gym 20p nua",
    "description": "Test tu JARVIS J3C-C",
    "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
    "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
    "reminders": {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 30},
            {"method": "popup", "minutes": 15},
            {"method": "popup", "minutes": 5},
        ],
    },
}

print(f"[Test] Creating event:")
print(f"  Title:   {event['summary']}")
print(f"  Start:   {start.isoformat()}")
print(f"  End:     {end.isoformat()}")
print(f"  Reminders: 30p / 15p / 5p popup")
print()

try:
    result = service.events().insert(calendarId=CAL_ID, body=event).execute()
    print("[OK] Event created!")
    print(f"  ID:       {result.get('id')}")
    print(f"  Link:     {result.get('htmlLink')}")
    print(f"  Start:    {result.get('start')}")
    print(f"  Reminders: {result.get('reminders')}")

    # Verify
    ev_check = service.events().get(calendarId=CAL_ID, eventId=result['id']).execute()
    reminders = ev_check.get("reminders", {})
    overrides = reminders.get("overrides", [])
    print(f"\n[Verify] Reminders fetched: {[(o['method'], o['minutes']) for o in overrides]}")

    # Cleanup
    service.events().delete(calendarId=CAL_ID, eventId=result['id']).execute()
    print(f"[Cleanup] Deleted test event")
except Exception as e:
    print(f"[ERR] {e}")
    import traceback
    traceback.print_exc()