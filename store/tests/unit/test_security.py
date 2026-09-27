"""Unit tests - Security scanner"""
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.security import scan_css, compute_hash


def test_scan_safe_css():
    css = ".btn { color: red; padding: 10px; }"
    result = scan_css(css)
    assert result is not None


def test_scan_dangerous_expression():
    css = ".x { width: expression(alert(1)); }"
    result = scan_css(css)
    d = result.to_dict() if hasattr(result, "to_dict") else result
    threats = d.get("threats") or []
    assert len(threats) > 0 or d.get("safe") is False


def test_scan_js_in_css():
    css = ".x { background: url(javascript:alert(1)); }"
    result = scan_css(css)
    d = result.to_dict() if hasattr(result, "to_dict") else result
    threats = d.get("threats") or []
    assert len(threats) > 0 or d.get("safe") is False


def test_compute_hash_file_consistent():
    """Hash cung 1 file phai giong nhau."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("hello world")
        path = f.name
    try:
        h1 = compute_hash(path)
        h2 = compute_hash(path)
        assert h1 == h2
    finally:
        os.unlink(path)


def test_compute_hash_file_different():
    """2 file khac content -> hash khac."""
    paths = []
    try:
        for content in ["hello", "world"]:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(content)
                paths.append(f.name)
        h1 = compute_hash(paths[0])
        h2 = compute_hash(paths[1])
        assert h1 != h2
    finally:
        for p in paths:
            os.unlink(p)


def test_compute_hash_length():
    """SHA256 = 64 hex chars."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test")
        path = f.name
    try:
        h = compute_hash(path)
        assert len(h) == 64
    finally:
        os.unlink(path)