# store/backend/github_oauth.py
"""
GitHub OAuth — Login with GitHub
"""
import os
import httpx
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
import jwt

from .database import get_db


router = APIRouter()

# Config
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "cognicraft-secret-change-in-production-2026")
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 30

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cognicraft-store.pages.dev")
BACKEND_URL = os.getenv("BACKEND_URL", "https://web-production-8b760.up.railway.app")


# ============================================================
# HELPERS
# ============================================================
def create_session_token(user_id: str, email: str, name: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


# ============================================================
# GET /github — Redirect to GitHub
# ============================================================
@router.get("/github")
async def github_login():
    """Redirect user tới GitHub OAuth authorize"""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(500, "GITHUB_CLIENT_ID chưa cấu hình")

    callback = f"{BACKEND_URL}/api/auth/github/callback"
    scope = "read:user user:email"
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={callback}"
        f"&scope={scope}"
    )
    return RedirectResponse(url)


# ============================================================
# GET /github/callback — Exchange code → user
# ============================================================
@router.get("/github/callback")
async def github_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Nhận code từ GitHub → exchange token → tạo user"""
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error={error}")
    if not code:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=missing_code")

    # 1. Exchange code → access token
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    if token_res.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=token_exchange_failed")

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=no_access_token")

    # 2. Fetch user info
    async with httpx.AsyncClient(timeout=15.0) as client:
        user_res = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )

    if user_res.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/?auth_error=fetch_user_failed")

    gh_user = user_res.json()
    github_id = str(gh_user["id"])
    login = gh_user["login"]
    name = gh_user.get("name") or login
    avatar = gh_user.get("avatar_url", "")
    email = gh_user.get("email")

    # 3. Nếu email private → fetch emails
    if not email:
        async with httpx.AsyncClient(timeout=15.0) as client:
            email_res = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if email_res.status_code == 200:
            emails = email_res.json()
            primary = next((e for e in emails if e.get("primary")), None)
            if primary:
                email = primary["email"]

    if not email:
        email = f"{login}@users.noreply.github.com"

    # 4. Upsert user
    db = get_db()
    user = db.query_one("SELECT * FROM public.users WHERE github_id = %s", (github_id,))

    if user:
        db.execute(
            "UPDATE public.users SET last_login = NOW(), name = %s, avatar_url = %s, github_username = %s WHERE id = %s",
            (name, avatar, login, user["id"]),
        )
        user_id = user["id"]
    else:
        existing_email = db.query_one("SELECT id FROM public.users WHERE email = %s", (email,))
        if existing_email:
            db.execute(
                "UPDATE public.users SET github_id = %s, github_username = %s, last_login = NOW() WHERE id = %s",
                (github_id, login, existing_email["id"]),
            )
            user_id = existing_email["id"]
        else:
            new_user = db.execute_returning(
                """
                INSERT INTO public.users (github_id, github_username, email, name, avatar_url, created_at, last_login)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (github_id, login, email, name, avatar),
            )
            user_id = new_user["id"]

    # 5. Create session JWT
    session_token = create_session_token(str(user_id), email, name)

    # 6. Redirect về frontend
    return RedirectResponse(f"{FRONTEND_URL}/?auth_token={session_token}")