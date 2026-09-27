"""License module - Sinh + verify license key cho theme paid"""
import os
import secrets
import string
from fastapi import APIRouter, HTTPException, Depends

from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/license", tags=["license"])

KEY_CHARS = string.ascii_uppercase + string.digits


def generate_license_key() -> str:
    def block():
        return ''.join(secrets.choice(KEY_CHARS) for _ in range(4))
    return f"COGNI-{block()}-{block()}-{block()}-{block()}"


def _get_user_id(user: dict) -> str:
    uid = user.get("id") or user.get("sub")
    if not uid:
        raise HTTPException(401, "Khong xac dinh duoc user_id")
    return str(uid)


def create_license_for_order(user_id: str, theme_slug: str, order_id: str):
    db = get_db()
    existing = db.query_one(
        "SELECT license_key FROM licenses WHERE user_id=%s AND theme_slug=%s AND status='active'",
        (user_id, theme_slug),
    )
    if existing:
        return None
    for _ in range(5):
        key = generate_license_key()
        try:
            db.execute(
                """INSERT INTO licenses (user_id, theme_slug, order_id, license_key, status)
                   VALUES (%s, %s, %s, %s, 'active')""",
                (user_id, theme_slug, order_id, key),
            )
            return key
        except Exception as e:
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                continue
            raise
    raise RuntimeError("Khong sinh duoc license key sau 5 lan thu")


@router.get("/me")
async def get_my_licenses(user: dict = Depends(get_current_user)):
    user_id = _get_user_id(user)
    db = get_db()
    rows = db.query(
        """SELECT l.id, l.theme_slug, l.license_key, l.status,
                  l.applied_count, l.last_applied_at, l.created_at,
                  p.name AS theme_name, p.icon AS theme_icon, p.is_paid
           FROM licenses l
           LEFT JOIN plugins p ON p.slug = l.theme_slug
           WHERE l.user_id = %s
           ORDER BY l.created_at DESC""",
        (user_id,),
    )
    return {"licenses": rows, "count": len(rows)}


@router.get("/verify/{theme_slug}")
async def verify_license(theme_slug: str, user: dict = Depends(get_current_user)):
    user_id = _get_user_id(user)
    db = get_db()
    row = db.query_one(
        """SELECT id, license_key, status, applied_count, last_applied_at
           FROM licenses
           WHERE user_id=%s AND theme_slug=%s AND status='active'""",
        (user_id, theme_slug),
    )
    if not row:
        return {"has_license": False}
    return {
        "has_license": True,
        "license_key": row["license_key"],
        "applied_count": row["applied_count"],
        "last_applied_at": row["last_applied_at"].isoformat() if row["last_applied_at"] else None,
    }


@router.post("/apply/{theme_slug}")
async def mark_license_applied(theme_slug: str, user: dict = Depends(get_current_user)):
    user_id = _get_user_id(user)
    db = get_db()
    db.execute(
        """UPDATE licenses 
           SET applied_count = applied_count + 1, last_applied_at = NOW()
           WHERE user_id=%s AND theme_slug=%s AND status='active'""",
        (user_id, theme_slug),
    )
    return {"ok": True}
