"""Integration tests - License API"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_license_me_unauthorized():
    res = client.get("/api/license/me")
    assert res.status_code == 401


def test_license_me_bad_token():
    res = client.get("/api/license/me", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == 401


def test_license_verify_unauthorized():
    res = client.get("/api/license/verify/golden-premium")
    assert res.status_code == 401


def test_license_apply_unauthorized():
    res = client.post("/api/license/apply/golden-premium")
    assert res.status_code == 401


def test_license_routes_exist():
    paths = list(app.openapi()["paths"].keys())
    assert "/api/license/me" in paths
    assert "/api/license/verify/{theme_slug}" in paths
    assert "/api/license/apply/{theme_slug}" in paths