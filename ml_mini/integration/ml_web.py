# ml_mini/integration/ml_web.py
"""
ML Web API - Đọc state từ file (shared với bot process)
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Paths
_BOT_ROOT = Path(__file__).parent.parent.parent.resolve()
_STATE_FILE = _BOT_ROOT / "ml_state" / "coordinator_state.json"


def _load_state() -> dict:
    """Đọc state từ file bot đã save"""
    if not _STATE_FILE.exists():
        return {
            "sandboxes": {},
            "links": [],
            "stats": {},
            "events": [],
        }

    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ML Web] Load state error: {e}")
        return {"sandboxes": {}, "links": [], "stats": {}, "events": []}


@router.get("/api/status")
async def ml_status():
    """Trạng thái toàn ML Mini (đọc từ file)"""
    state = _load_state()

    sandboxes = state.get("sandboxes", {})
    links = state.get("links", [])

    # Build states map
    states = {sid: sb.get("state", "healthy") for sid, sb in sandboxes.items()}

    # Stats
    healthy = sum(1 for s in states.values() if s == "healthy")
    down = sum(1 for s in states.values() if s == "down")
    recovering = sum(1 for s in states.values() if s == "recovering")

    # Build sandbox details
    sb_details = {}
    for sid, sb in sandboxes.items():
        sb_details[sid] = {
            "name": sb.get("name", sid),
            "state": sb.get("state", "healthy"),
            "restart_count": sb.get("restart_count", 0),
            "missed_heartbeats": 0,
            "restart_attempts": 0,
            "heartbeat_interval": 15,
        }

    return {
        "total_sandboxes": len(sandboxes),
        "total_links": len(links),
        "states": states,
        "sandboxes": sb_details,
        "links": links,
        "stats": {
            "healthy": healthy,
            "down": down,
            "recovering": recovering,
            "dead": 0,
        },
        "heartbeat": {},
    }


@router.get("/api/events")
async def ml_events(limit: int = 20):
    """Event log"""
    state = _load_state()
    events = state.get("events", [])
    return {"events": events[-limit:]}


@router.get("/api/predict/{member}")
async def ml_predict(member: str, weeks: int = 4):
    """Predict scores (từ bot process)"""
    return {
        "error": "ML predictions available từ bot process",
        "hint": f"Chạy `!ml_predict {member} {weeks}` trong Discord",
    }


@router.get("/api/anomaly")
async def ml_anomaly(member: str = None):
    """Detect anomalies"""
    return {
        "error": "Anomaly detection available từ bot process",
        "hint": "Chạy `!ml_anomaly` trong Discord",
    }


@router.get("/api/tokens")
async def ml_tokens(task: str, prompt_length: int = 1500):
    """Predict tokens"""
    return {
        "error": "Token prediction available từ bot process",
        "hint": f"Chạy `!ml_tokens {task}` trong Discord",
    }