"""Unit tests - License key generation"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.license import generate_license_key


def test_license_key_format():
    key = generate_license_key()
    pattern = r"^COGNI-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
    assert re.match(pattern, key), f"Bad format: {key}"


def test_license_key_length():
    key = generate_license_key()
    assert len(key) == 25


def test_license_key_unique():
    keys = {generate_license_key() for _ in range(100)}
    assert len(keys) == 100


def test_license_prefix():
    key = generate_license_key()
    assert key.startswith("COGNI-")


def test_license_4_blocks():
    key = generate_license_key()
    parts = key.split("-")
    assert len(parts) == 5
    assert parts[0] == "COGNI"
    for p in parts[1:]:
        assert len(p) == 4