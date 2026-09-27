"""Payment module - PayOS 1.1.0"""
import os
import time
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user
from .license import create_license_for_order

from payos import PayOS
from payos.types import CreatePaymentLinkRequest

router = APIRouter(prefix="/api/payment", tags=["payment"])


def get_payos_client() -> PayOS:
    client_id = os.getenv("PAYOS_CLIENT_ID")
    api_key = os.getenv("PAYOS_API_KEY")
    checksum_key = os.getenv("PAYOS_CHECKSUM_KEY")
    if not all([client_id, api_key, checksum_key]):
        raise HTTPException(500, "Thieu PayOS credentials trong env")
    return PayOS(client_id=client_id, api_key=api_key, checksum_key=checksum_key)


def _get_user_id(user: dict) -> str:
    uid = user.get("id") or user.get("sub")
    if not uid:
        raise HTTPException(401, "Khong xac dinh duoc user_id")
    return str(uid)


class CreatePaymentRequest(BaseModel):
    theme_slug: str


@router.post("/create")
async def create_payment(req: CreatePaymentRequest, user: dict = Depends(get_current_user)):
    user_id = _get_user_id(user)
    db = get_db()

    theme = db.query_one(
        "SELECT slug, name, price_vnd, is_paid FROM plugins WHERE slug=%s AND type='theme'",
        (req.theme_slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme khong ton tai")
    if not theme.get("is_paid") or (theme.get("price_vnd") or 0) <= 0:
        raise HTTPException(400, "Theme mien phi")

    existing = db.query_one(
        "SELECT id FROM orders WHERE user_id=%s AND theme_slug=%s AND status='paid'",
        (user_id, req.theme_slug),
    )
    if existing:
        raise HTTPException(400, "Ban da so huu theme nay roi")

    order_code = int(time.time()) % 1000000000

    order_row = db.execute_returning(
        """INSERT INTO orders (user_id, theme_slug, amount_vnd, status, payment_ref)
           VALUES (%s, %s, %s, 'pending', %s) RETURNING id""",
        (user_id, req.theme_slug, theme["price_vnd"], str(order_code)),
    )
    if not order_row:
        raise HTTPException(500, "Khong tao duoc order")

    order_id = order_row["id"]

    try:
        payos = get_payos_client()
        payment_request = CreatePaymentLinkRequest(
            orderCode=order_code,
            amount=int(theme["price_vnd"]),
            description="Mua " + theme["name"][:20],
            cancelUrl=os.getenv("PAYOS_CANCEL_URL", "http://localhost:8001/store/payment-cancel.html"),
            returnUrl=os.getenv("PAYOS_RETURN_URL", "http://localhost:8001/store/payment-success.html"),
        )
        result = payos.payment_requests.create(payment_request)

        checkout_url = getattr(result, "checkout_url", None) or getattr(result, "checkoutUrl", None)
        payment_link_id = getattr(result, "payment_link_id", None) or getattr(result, "paymentLinkId", None)

        if not checkout_url:
            raise HTTPException(500, "PayOS khong tra ve checkout_url")

        db.execute("UPDATE orders SET payment_ref=%s WHERE id=%s", (str(order_code), order_id))

        return {"checkout_url": checkout_url, "order_code": order_code, "amount": int(theme["price_vnd"])}

    except HTTPException:
        db.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        raise
    except Exception as e:
        db.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        raise HTTPException(500, "Loi tao link PayOS: " + str(e))


@router.post("/webhook")
async def payos_webhook(request: Request):
    try:
        body = await request.json()
        payos = get_payos_client()
        webhook_data = payos.verifyPaymentWebhookData(body)

        order_code = getattr(webhook_data, "order_code", None) or getattr(webhook_data, "orderCode", None)
        if not order_code:
            return {"error": 1, "message": "Missing order_code", "data": {}}

        db = get_db()
        updated = db.execute_returning(
            """UPDATE orders SET status='paid', paid_at=NOW()
               WHERE payment_ref=%s AND status='pending'
               RETURNING id, user_id, theme_slug""",
            (str(order_code),),
        )
        if updated:
            print("Order " + str(updated["id"]) + " paid - user " + str(updated["user_id"]))
            try:
                key = create_license_for_order(
                    str(updated["user_id"]),
                    updated["theme_slug"],
                    str(updated["id"]),
                )
                if key:
                    print("LICENSE generated: " + key)
                else:
                    print("LICENSE da ton tai")
            except Exception as e:
                print("LICENSE error: " + str(e))
        return {"error": 0, "message": "OK", "data": {}}
    except Exception as e:
        print("Webhook error: " + str(e))
        return {"error": 1, "message": str(e), "data": {}}


@router.get("/order/{order_code}")
async def get_order_status(order_code: str, user: dict = Depends(get_current_user)):
    user_id = _get_user_id(user)
    db = get_db()
    row = db.query_one(
        """SELECT id, status, theme_slug, amount_vnd, paid_at
           FROM orders WHERE payment_ref=%s AND user_id=%s""",
        (order_code, user_id),
    )
    if not row:
        raise HTTPException(404, "Khong tim thay don hang")
    return {
        "order_id": str(row["id"]),
        "status": row["status"],
        "theme_slug": row["theme_slug"],
        "amount_vnd": row["amount_vnd"],
        "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
    }
