"""The one job format every collector produces."""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field


@dataclass
class Job:
    platform: str                 # "JobStreet", "Indeed", "LinkedIn", "Kalibrr"
    platform_id: str              # id on that platform
    title: str
    company: str
    url: str
    location: str = ""
    posted_at: str = ""           # ISO-8601 UTC, e.g. 2026-11-09T08:43:19Z
    posted_precision: str = "exact"   # "exact" (date+time), "hour" (approx, from "5 hours ago"), "date"
    salary: str = ""
    work_type: str = ""           # Full time / Contract ...
    description: str = ""         # plain text
    address: str = ""             # office / work address when the source gives one
    company_url: str = ""
    # filled in by the pipeline
    roles: list[str] = field(default_factory=list)
    resume: str = ""
    area: str = ""                # Metro Manila / Cavite / ...
    experience: str = ""          # "Fresh graduates OK" / "Less than 1 year" / "Needs 2+ years" / "Experience not mentioned"
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    hidden_reason: str = ""       # "" = shown; otherwise why it is hidden
    also_on: list[dict] = field(default_factory=list)   # duplicates on other platforms
    first_seen: str = ""

    def to_dict(self):
        return asdict(self)


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h\d|tr)[^>]*>", re.I)


def html_to_text(s: str) -> str:
    """Rough HTML → readable plain text (keeps line breaks between blocks/bullets)."""
    if not s:
        return ""
    s = _BLOCK.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()
