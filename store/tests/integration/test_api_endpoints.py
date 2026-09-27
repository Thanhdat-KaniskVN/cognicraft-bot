"""Integration tests - Store, Marketplace, Payment"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ===== STORE =====
def test_store_plugins_list():
    res = client.get("/api/store/plugins")
    assert res.status_code == 200


def test_store_categories():
    res = client.get("/api/store/categories")
    assert res.status_code == 200


def test_store_stats():
    res = client.get("/api/store/stats")
    assert res.status_code == 200


# ===== MARKETPLACE =====
def test_marketplace_themes_list():
    res = client.get("/api/marketplace/themes")
    assert res.status_code == 200


def test_marketplace_tags():
    res = client.get("/api/marketplace/tags")
    assert res.status_code == 200


# ===== PAYMENT =====
def test_payment_create_unauthorized():
    res = client.post("/api/payment/create", json={"theme_slug": "golden-premium"})
    assert res.status_code == 401


def test_payment_order_unauthorized():
    res = client.get("/api/payment/order/123456")
    assert res.status_code == 401


def test_payment_webhook_exists():
    """Webhook phai ton tai (405 khi GET)."""
    res = client.get("/api/payment/webhook")
    assert res.status_code == 405


# ===== AUTH =====
def test_auth_me_unauthorized():
    res = client.get("/api/auth/me")
    assert res.status_code == 401


# ===== PRESENCE =====
def test_presence_list_unauthorized():
    """Presence list yeu cau auth -> 401."""
    res = client.get("/api/presence/list")
    assert res.status_code == 401


# ===== SECURITY =====
def test_security_health():
    res = client.get("/api/security/health")
    assert res.status_code == 200