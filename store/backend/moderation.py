"""Moderation module - Duyet theme/plugin truoc khi public"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/admin/moderation", tags=["moderation"])


def _check_admin(user: dict):
    """Check user co phai admin khong."""
    db = get_db()
    user_id = user.get("id") or user.get("sub")
    row = db.query_one(
        "SELECT is_admin FROM public.users WHERE id=%s",
        (str(user_id),),
    )
    if not row or not row.get("is_admin"):
        raise HTTPException(403, "Chi admin moi duoc truy cap")
    return user_id


class ModerationAction(BaseModel):
    note: str = ""


# ===== Queue =====
@router.get("/queue")
async def get_queue(user: dict = Depends(get_current_user)):
    """List tat ca item dang cho duyet."""
    _check_admin(user)
    db = get_db()
    rows = db.query(
        """SELECT id, slug, name, type, author, author_email,
                  description, category, tags, icon, preview_image,
                  price_vnd, is_paid, css_content, created_at
           FROM plugins
           WHERE moderation_status = 'pending'
           ORDER BY created_at ASC"""
    )
    return {"items": rows, "count": len(rows)}


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    """Lich su duyet gan day."""
    _check_admin(user)
    db = get_db()
    rows = db.query(
        """SELECT slug, name, type, author, moderation_status,
                  moderation_note, moderated_at
           FROM plugins
           WHERE moderation_status IN ('approved', 'rejected', 'changes_requested')
           ORDER BY moderated_at DESC NULLS LAST
           LIMIT 50"""
    )
    return {"items": rows, "count": len(rows)}


# ===== Actions =====
@router.post("/{slug}/approve")
async def approve_item(slug: str, user: dict = Depends(get_current_user)):
    """Duyet item -> hien tren marketplace."""
    admin_id = _check_admin(user)
    db = get_db()

    row = db.query_one(
        "SELECT slug, name FROM plugins WHERE slug=%s",
        (slug,),
    )
    if not row:
        raise HTTPException(404, "Khong tim thay item")

    db.execute(
        """UPDATE plugins 
           SET moderation_status='approved',
               moderation_note=NULL,
               moderated_by=%s,
               moderated_at=NOW()
           WHERE slug=%s""",
        (str(admin_id), slug),
    )
    return {"ok": True, "slug": slug, "status": "approved"}


@router.post("/{slug}/reject")
async def reject_item(slug: str, body: ModerationAction, user: dict = Depends(get_current_user)):
    """Tu choi item - author se thay ly do."""
    admin_id = _check_admin(user)
    db = get_db()

    if not body.note.strip():
        raise HTTPException(400, "Phai co ly do tu choi")

    row = db.query_one("SELECT slug FROM plugins WHERE slug=%s", (slug,))
    if not row:
        raise HTTPException(404, "Khong tim thay item")

    db.execute(
        """UPDATE plugins 
           SET moderation_status='rejected',
               moderation_note=%s,
               moderated_by=%s,
               moderated_at=NOW()
           WHERE slug=%s""",
        (body.note.strip(), str(admin_id), slug),
    )
    return {"ok": True, "slug": slug, "status": "rejected"}


@router.post("/{slug}/request-changes")
async def request_changes(slug: str, body: ModerationAction, user: dict = Depends(get_current_user)):
    """Yeu cau author sua truoc khi duyet."""
    admin_id = _check_admin(user)
    db = get_db()

    if not body.note.strip():
        raise HTTPException(400, "Phai co ghi chu yeu cau sua")

    row = db.query_one("SELECT slug FROM plugins WHERE slug=%s", (slug,))
    if not row:
        raise HTTPException(404, "Khong tim thay item")

    db.execute(
        """UPDATE plugins 
           SET moderation_status='changes_requested',
               moderation_note=%s,
               moderated_by=%s,
               moderated_at=NOW()
           WHERE slug=%s""",
        (body.note.strip(), str(admin_id), slug),
    )
    return {"ok": True, "slug": slug, "status": "changes_requested"}


# ===== Author view =====
@router.get("/my-items")
async def get_my_items(user: dict = Depends(get_current_user)):
    """Author xem status cac item cua minh."""
    user_id = user.get("id") or user.get("sub")
    db = get_db()
    row = db.query_one(
        "SELECT email, name FROM public.users WHERE id=%s",
        (str(user_id),),
    )
    if not row:
        raise HTTPException(404, "Khong tim thay user")

    email = row.get("email")
    name = row.get("name")

    rows = db.query(
        """SELECT slug, name, type, moderation_status, moderation_note,
                  moderated_at, created_at, is_paid, price_vnd
           FROM plugins
           WHERE author_email=%s OR author=%s
           ORDER BY created_at DESC""",
        (email, name),
    )
    return {"items": rows, "count": len(rows)}