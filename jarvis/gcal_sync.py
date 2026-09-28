# jarvis/gcal_sync.py
"""Push events len GCal qua Switch Railway."""
import os
import httpx
from datetime import datetime
from typing import Optional

SWITCH_URL = os.getenv(
    "SWITCH_URL",
    "https://cognicraft-switch-production.up.railway.app"
)


async def push_event_async(title, start_dt, end_dt, description="", location=None,
                            reminders=None, timeout=15.0) -> Optional[dict]:
    """Async: push event len Switch -> GCal.

    Returns {id, htmlLink} hoac None.
    """
    if reminders is None:
        reminders = [30, 15, 5]

    if start_dt.tzinfo is None:
        import pytz
        start_dt = pytz.timezone("Asia/Ho_Chi_Minh").localize(start_dt)
    if end_dt.tzinfo is None:
        import pytz
        end_dt = pytz.timezone("Asia/Ho_Chi_Minh").localize(end_dt)

    body = {
        "socket": "google_calendar",
        "action": "add_event",
        "params": {
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "description": description or "",
            "timezone": "Asia/Ho_Chi_Minh",
            "reminders": reminders,
        },
    }
    if location:
        body["params"]["location"] = location

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{SWITCH_URL}/panel/call", json=body)
            r.raise_for_status()
            data = r.json()
            if not data.get("success"):
                print(f"[GCalSync] Switch error: {data.get('error')}")
                return None
            result = data.get("result") or {}
            return {
                "id": result.get("id"),
                "htmlLink": result.get("htmlLink"),
            }
    except httpx.TimeoutException:
        print("[GCalSync] Timeout")
        return None
    except Exception as e:
        print(f"[GCalSync] Error: {e}")
        return None


async def delete_event_async(gcal_id, timeout=15.0) -> bool:
    body = {
        "socket": "google_calendar",
        "action": "delete_event",
        "params": {"event_id": gcal_id},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{SWITCH_URL}/panel/call", json=body)
            r.raise_for_status()
            return r.json().get("success", False)
    except Exception as e:
        print(f"[GCalSync] delete error: {e}")
        return False


if __name__ == "__main__":
    import asyncio, sys
    from datetime import timedelta
    from dotenv import load_dotenv
    load_dotenv()

    async def _test():
        print("=" * 60)
        print(f"GCAL SYNC TEST (SWITCH_URL={SWITCH_URL})")
        print("=" * 60)
        now = datetime.now()
        start = now + timedelta(minutes=25)
        end = start + timedelta(minutes=60)
        r = await push_event_async(
            "[TEST-JARVIS] Gym 25p nua", start, end,
            description="Test tu gcal_sync module"
        )
        if r:
            print(f"[OK] id={r['id']}")
            print(f"     link={r['htmlLink']}")
            await delete_event_async(r["id"])
            print("[Cleanup] Deleted")
        else:
            print("[FAIL] push returned None")

    asyncio.run(_test())