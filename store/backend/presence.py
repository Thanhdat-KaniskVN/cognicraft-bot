# store/backend/presence.py
"""
User Presence System
- Heartbeat ping
- Online/offline/away/invisible status
- List online users
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user

router = APIRouter()

# Config
ONLINE_WINDOW_SECONDS = 60   # Trong 60s coi như online
HEARTBEAT_INTERVAL = 30      # Frontend ping mỗi 30s


# ============================================================
# MODELS
# ============================================================
class StatusUpdateRequest(BaseModel):
    status: Optional[str] = None         # 'online' | 'away' | 'invisible' | 'offline'
    show_online: Optional[bool] = None   # True = hiện trong list, False = ẩn


# ============================================================
# HELPERS
# ============================================================
def utc_now_aware():
    """Timezone-aware UTC now — match TIMESTAMPTZ từ PostgreSQL"""
    return datetime.now(timezone.utc)


def to_aware_utc(dt):
    """Normalize datetime về aware UTC"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============================================================
# POST /api/presence/ping — Heartbeat
# ============================================================
@router.post("/ping")
async def ping(user: dict = Depends(get_current_user)):
    """
    Frontend gọi mỗi 30s để báo 'tôi đang online'.
    Tự upsert vào user_presence.
    """
    db = get_db()
    user_id = user["sub"]

    db.execute(
        """
        INSERT INTO user_presence (user_id, status, last_seen, updated_at)
        VALUES (%s, 'online', NOW(), NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET last_seen = NOW(),
            updated_at = NOW(),
            status = CASE 
                WHEN user_presence.status = 'invisible' THEN 'invisible'
                ELSE 'online'
            END
        """,
        (user_id,),
    )

    return {
        "success": True,
        "server_time": utc_now_aware().isoformat(),
    }


# ============================================================
# GET /api/presence/list — Danh sách user
# ============================================================
@router.get("/list")
async def list_presence(user: dict = Depends(get_current_user)):
    """
    Trả về danh sách users kèm trạng thái.
    Chỉ hiện user có show_online = TRUE.
    """
    db = get_db()

    # Dùng timezone-aware cutoff để match với TIMESTAMPTZ
    cutoff = utc_now_aware() - timedelta(seconds=ONLINE_WINDOW_SECONDS)

    rows = db.query(
        """
        SELECT 
            u.id,
            u.name,
            u.email,
            u.avatar_url,
            u.github_username,
            u.bio,
            COALESCE(p.status, 'offline') AS status,
            COALESCE(p.show_online, TRUE) AS show_online,
            p.last_seen
        FROM public.users u
        LEFT JOIN user_presence p ON p.user_id = u.id
        WHERE COALESCE(p.show_online, TRUE) = TRUE
        ORDER BY p.last_seen DESC NULLS LAST, u.name ASC
        LIMIT 200
        """,
    )

    online = []
    offline = []

    for r in rows:
        last_seen = r.get("last_seen")
        last_seen_aware = to_aware_utc(last_seen)

        is_online = False
        if last_seen_aware is not None:
            is_online = (
                last_seen_aware >= cutoff
                and r.get("status") not in ("offline", "invisible")
            )

        user_obj = {
            "id": str(r["id"]),
            "name": r.get("name"),
            "email": r.get("email"),
            "avatar_url": r.get("avatar_url"),
            "github_username": r.get("github_username"),
            "bio": r.get("bio"),
            "status": "online" if is_online else "offline",
            "last_seen": last_seen.isoformat() if last_seen else None,
        }

        if is_online:
            online.append(user_obj)
        else:
            offline.append(user_obj)

    return {
        "online_count": len(online),
        "offline_count": len(offline),
        "online": online,
        "offline": offline[:50],
    }


# ============================================================
# GET /api/presence/me — Trạng thái của mình
# ============================================================
@router.get("/me")
async def get_my_presence(user: dict = Depends(get_current_user)):
    """Xem trạng thái presence của chính mình"""
    db = get_db()

    row = db.query_one(
        "SELECT * FROM user_presence WHERE user_id = %s",
        (user["sub"],),
    )

    if not row:
        return {
            "status": "offline",
            "show_online": True,
            "last_seen": None,
        }

    return {
        "status": row.get("status", "offline"),
        "show_online": row.get("show_online", True),
        "last_seen": row["last_seen"].isoformat() if row.get("last_seen") else None,
    }


# ============================================================
# PUT /api/presence/status — Đổi status hoặc ẩn/hiện
# ============================================================
@router.put("/status")
async def update_status(
    req: StatusUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """
    Update status:
    - status: 'online' | 'away' | 'invisible' | 'offline'
    - show_online: True/False (ẩn hiện khỏi list)
    """
    db = get_db()
    user_id = user["sub"]

    # Validate status
    valid_statuses = {"online", "away", "invisible", "offline"}
    if req.status is not None and req.status not in valid_statuses:
        raise HTTPException(400, f"Status không hợp lệ. Chỉ chấp nhận: {valid_statuses}")

    db.execute(
        """
        INSERT INTO user_presence (user_id, status, show_online, last_seen, updated_at)
        VALUES (
            %s,
            COALESCE(%s, 'online'),
            COALESCE(%s, TRUE),
            NOW(),
            NOW()
        )
        ON CONFLICT (user_id) DO UPDATE
        SET status = COALESCE(%s, user_presence.status),
            show_online = COALESCE(%s, user_presence.show_online),
            last_seen = NOW(),
            updated_at = NOW()
        """,
        (
            user_id,
            req.status,
            req.show_online,
            req.status,
            req.show_online,
        ),
    )

    return {"success": True}


# ============================================================
# POST /api/presence/offline — Chủ động báo offline (khi logout)
# ============================================================
@router.post("/offline")
async def go_offline(user: dict = Depends(get_current_user)):
    """Set status = offline khi user logout hoặc rời trang"""
    db = get_db()
    db.execute(
        """
        INSERT INTO user_presence (user_id, status, last_seen, updated_at)
        VALUES (%s, 'offline', NOW(), NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET status = 'offline', last_seen = NOW(), updated_at = NOW()
        """,
        (user["sub"],),
    )
    return {"success": True}