"""Pull recruiter emails, phone numbers and an office address out of a job description."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# PH mobiles (09xx / +639xx) and Metro Manila landlines ((02) 8xxx-xxxx).
_PHONE = re.compile(
    r"(?:\+?63[\s-]?|0)9\d{2}[\s-]?\d{3}[\s-]?\d{4}"
    r"|\(?\+?(?:63[\s-]?)?\(?0?2\)?[\s-]?[78]\d{3}[\s-]?\d{4}"
)
_ADDRESS_LINE = re.compile(
    r"(?:office\s*address|company\s*address|work\s*(?:location|address)|address|job\s*site|"
    r"site\s*location|location\s*of\s*work|located\s*at|report\s*to)\s*[:\-–]\s*(.{8,160})",
    re.I,
)


def emails(text: str) -> list[str]:
    seen = []
    for e in _EMAIL.findall(text or ""):
        e = e.strip(".").lower()
        if e not in seen and not e.endswith((".png", ".jpg", ".jpeg", ".gif")):
            seen.append(e)
    return seen


def phones(text: str) -> list[str]:
    seen = []
    for p in _PHONE.findall(text or ""):
        p = re.sub(r"\s+", " ", p.strip())
        if p not in seen:
            seen.append(p)
    return seen


def address(text: str) -> str:
    m = _ADDRESS_LINE.search(text or "")
    if not m:
        return ""
    line = m.group(1).split("\n")[0].strip(" .;")
    return line
