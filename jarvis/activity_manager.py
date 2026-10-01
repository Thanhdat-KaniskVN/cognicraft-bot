# jarvis/activity_manager.py
"""CRUD cho jarvis_activities - khong phai event, la knowledge entity."""
from datetime import datetime
from typing import List, Optional

import psycopg2.extras
from database import get_cursor


ACTIVITY_TYPES = ["course", "project", "routine", "exam", "meeting", "hobby", "other"]


def _slugify(text: str) -> str:
    import unicodedata, re
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("\u0111", "d").replace("\u0110", "D").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:50]


def create_activity(slug: str, name: str, activity_type: str = "other",
                    description: str = None, owner_id: str = None,
                    metadata: dict = None) -> Optional[int]:
    if activity_type not in ACTIVITY_TYPES:
        activity_type = "other"

    slug = _slugify(slug) if slug else _slugify(name)
    if not slug:
        return None

    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO jarvis_activities
            (slug, name, activity_type, description, owner_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                activity_type = EXCLUDED.activity_type,
                description = EXCLUDED.description,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
        """, (slug, name, activity_type, description, owner_id,
              psycopg2.extras.Json(metadata or {})))
        row = cur.fetchone()
        return row["id"] if row else None


def get_activity(slug: str) -> Optional[dict]:
    slug = _slugify(slug)
    with get_cursor() as cur:
        cur.execute("SELECT * FROM jarvis_activities WHERE slug = %s", (slug,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_activity_by_id(activity_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM jarvis_activities WHERE id = %s", (activity_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_activities(activity_type: str = None, limit: int = 50) -> List[dict]:
    sql = "SELECT * FROM jarvis_activities"
    params = []
    if activity_type:
        sql += " WHERE activity_type = %s"
        params.append(activity_type)
    sql += " ORDER BY updated_at DESC LIMIT %s"
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_activity(slug: str, **fields) -> bool:
    if not fields:
        return False
    allowed = {"name", "activity_type", "description", "metadata"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = psycopg2.extras.Json(updates["metadata"])
    if not updates:
        return False
    updates["updated_at"] = datetime.now()

    cols = ", ".join(f"{k} = %s" for k in updates.keys())
    vals = list(updates.values()) + [_slugify(slug)]

    with get_cursor() as cur:
        cur.execute(f"UPDATE jarvis_activities SET {cols} WHERE slug = %s", tuple(vals))
        return cur.rowcount > 0


def delete_activity(slug: str) -> bool:
    slug = _slugify(slug)
    with get_cursor() as cur:
        cur.execute("DELETE FROM jarvis_activities WHERE slug = %s", (slug,))
        return cur.rowcount > 0


def search_activities(query: str, limit: int = 10) -> List[dict]:
    """Tim activity theo ten/slug."""
    import unicodedata, re
    q = unicodedata.normalize("NFD", query)
    q = "".join(c for c in q if unicodedata.category(c) != "Mn").lower()
    q = q.replace("\u0111", "d")

    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM jarvis_activities
            WHERE LOWER(slug) LIKE %s
               OR LOWER(name) LIKE %s
            ORDER BY updated_at DESC
            LIMIT %s
        """, (f"%{q}%", f"%{q}%", limit))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("ACTIVITY MANAGER TEST")
    print("=" * 60)

    # Cleanup
    for a in list_activities(limit=100):
        if a["slug"].startswith("test-"):
            delete_activity(a["slug"])

    # Create
    aid = create_activity("MAE101", "Mon MAE101 - Toan cho ky thuat",
                          activity_type="course",
                          description="Mathematics for Engineering")
    print(f"[Create] id={aid}")

    # Read
    a = get_activity("mae101")
    print(f"[Read] {a['slug']} | {a['name']} | {a['activity_type']}")

    # Update
    update_activity("mae101", description="Updated description")
    a = get_activity("mae101")
    print(f"[Update] {a['description']}")

    # Search
    results = search_activities("mae")
    print(f"[Search 'mae'] {len(results)} results")

    # List
    all_acts = list_activities()
    print(f"[List] {len(all_acts)} activities")

    # Cleanup
    delete_activity("mae101")
    print(f"[Cleanup] Done")