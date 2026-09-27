"""Basic tests - health check, imports"""
import sys
from pathlib import Path

# Add store/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Tat ca module chinh phai import duoc."""
    from backend import api, auth, database, models, payment, license, security
    assert api.router is not None
    assert auth.router is not None
    assert payment.router is not None
    assert license.router is not None


def test_main_app():
    """FastAPI app phai khoi tao duoc."""
    from main import app
    assert app is not None
    assert app.title == "CogniCraft Store API"


def test_health_endpoint():
    """GET /health phai tra 200."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_root_endpoint():
    """GET / phai tra info service."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "CogniCraft Store API"
