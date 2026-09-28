# jarvis/context_analyzer.py
"""Detect user context (sick, accident, tired, urgent) + severity."""
import re
import unicodedata
from typing import Optional


def _norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("\u0111", "d").replace("\u0110", "D").lower().strip()


CONTEXT_RULES = [
    ("accident", "critical", [r"\bte xe\b", r"\btai nan\b", r"\bte nga\b", r"\bgay tay\b", r"\bgay chan\b", r"\bxuong\b"]),
    ("family", "high", [r"\bgia dinh\b", r"\bnguoi than\b", r"\bme om\b", r"\bbo om\b", r"\bme benh\b", r"\bbo benh\b"]),
    ("sick_heavy", "high", [r"\bom nang\b", r"\bsot cao\b", r"\bnhap vien\b", r"\bcap cuu\b"]),
    ("sick", "high", [r"\bom\b", r"\bbenh\b", r"\bdau\b", r"\bsot\b", r"\bho\b", r"\bdau dau\b"]),
    ("tired", "medium", [r"\bmet moi\b", r"\bkiet suc\b", r"\bbuon ngu\b", r"\bmet\b", r"\bmoi\b"]),
    ("urgent", "high", [r"\bcong viec gap\b", r"\bviec gap\b", r"\bco viec\b", r"\bdot xuat\b", r"\bkhan cap\b", r"\bkhancap\b"]),
]


class UserContext:
    def __init__(self, context_type, severity, raw_text, matched_kw):
        self.context_type = context_type
        self.severity = severity
        self.raw_text = raw_text
        self.matched_kw = matched_kw

    def to_dict(self):
        return {
            "context_type": self.context_type,
            "severity": self.severity,
            "matched_kw": self.matched_kw,
        }

    def __repr__(self):
        return f"UserContext({self.context_type}/{self.severity})"


def detect_context(text):
    """Return UserContext or None."""
    if not text:
        return None
    n = _norm(text)
    for ctx_type, severity, patterns in CONTEXT_RULES:
        for pat in patterns:
            if re.search(pat, n):
                return UserContext(ctx_type, severity, text, pat)
    return None


if __name__ == "__main__":
    tests = [
        "toi om roi", "em bi sot cao qua", "te xe roi dau qua",
        "met moi qua", "co viec gap dot xuat", "gia dinh co chuyen",
        "hello world", "mai di hoc",
    ]
    for t in tests:
        print(f"  {t!r:40s} -> {detect_context(t)}")