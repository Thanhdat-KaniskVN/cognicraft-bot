# switch/sockets/google_calendar.py
"""
Google Calendar Socket - "Phích cắm Google"
"""
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.socket import Socket


SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarSocket(Socket):
    NAME = "google_calendar"
    TYPE = "external_service"
    VERSION = "1.0.0"
    DESCRIPTION = "Kết nối Google Calendar"

    async def _on_start(self) -> bool:
        creds_file = self.config.get("credentials_file", "credentials.json")
        token_file = self.config.get("token_file", "token.json")
        self.calendar_id = self.config.get("calendar_id", "primary")

        creds = None
        if Path(token_file).exists():
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(creds_file).exists():
                    raise FileNotFoundError(f"❌ {creds_file} không tìm thấy")
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_file, "w") as f:
                f.write(creds.to_json())

        self.service = build("calendar", "v3", credentials=creds)
        print(f"[GoogleCalendar] ✅ Connected (calendar: {self.calendar_id})")
        return True

    async def _on_stop(self):
        self.service = None

    async def _on_health(self) -> bool:
        try:
            await asyncio.to_thread(
                self.service.calendarList().get(calendarId=self.calendar_id).execute
            )
            return True
        except Exception:
            return False

    async def _on_call(self, action: str, **kwargs):
        if action == "add_event":
            return await self._add_event(**kwargs)
        elif action == "list_events":
            return await self._list_events(**kwargs)
        elif action == "delete_event":
            return await self._delete_event(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")

    # ============================================================
    # ACTIONS
    # ============================================================

    async def _add_event(self, title: str, date: str, description: str = "", **kwargs):
        event = {
            "summary": title,
            "description": description,
            "start": {"date": date},
            "end": {"date": date},
        }
        result = await asyncio.to_thread(
            self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
            ).execute
        )
        return {
            "id": result.get("id"),
            "htmlLink": result.get("htmlLink"),
            "summary": result.get("summary"),
        }

    async def _list_events(self, days: int = 30, max: int = 10):
        time_min = datetime.utcnow().isoformat() + "Z"
        time_max = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

        result = await asyncio.to_thread(
            self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max,
                singleEvents=True,
                orderBy="startTime",
            ).execute
        )
        return [
            {"id": e.get("id"), "summary": e.get("summary"), "start": e.get("start")}
            for e in result.get("items", [])
        ]

    async def _delete_event(self, event_id: str):
        await asyncio.to_thread(
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute
        )
        return {"deleted": event_id}