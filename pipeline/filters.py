"""Decide which roles a job fits, and whether it must be hidden (male-only, senior, overseas, ...)."""
from __future__ import annotations

import re

import config
from pipeline.model import Job

_ROLE_RE = {name: [re.compile(p, re.I) for p in r["title"]] for name, r in config.ROLES.items()}


def match_roles(title: str) -> list[str]:
    roles = [name for name, pats in _ROLE_RE.items() if any(p.search(title) for p in pats)]
    # "Civil Engineer (general)" only when nothing more specific matched.
    if len(roles) > 1 and "Civil Engineer (general)" in roles:
        roles.remove("Civil Engineer (general)")
    return roles


def is_male_restricted(text: str) -> bool:
    """True when the ad restricts to / prefers MALE applicants. Female-only ads return False."""
    if not text:
        return False
    cleaned = config.GENDER_INCLUSIVE.sub(" ", text)
    return any(p.search(cleaned) for p in config.MALE_ONLY_RE)


_YEARS = re.compile(
    r"(?:at\s*least|minimum\s*(?:of)?|min\.?|no\s*less\s*than)?\s*(\d{1,2})\s*(?:\+|\s*or\s*more)?\s*"
    r"(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\b(?:\s*of)?\s*(?:relevant|related|work|working|professional|"
    r"proven|solid|hands-on|progressive)?\s*(?:work\s*)?experience",
    re.I,
)


def required_years(text: str) -> list[int]:
    return [int(m.group(1)) for m in _YEARS.finditer(text or "")]


def is_senior(title: str, description: str) -> bool:
    if config.SENIOR_TITLE.search(title):
        return True
    years = required_years(description)
    # Senior only when EVERY experience requirement mentioned is >= the threshold
    # (ads often list several positions; keep it if any of them is junior-friendly).
    return bool(years) and min(years) >= config.SENIOR_MIN_YEARS


def area_of(location: str, address: str = "") -> str:
    text = f"{location} {address}".lower()
    for area, words in config.AREAS.items():
        if any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words):
            return area
    return ""


def is_overseas(job: Job) -> bool:
    if config.OVERSEAS.search(f"{job.title} {job.location}"):
        return True
    return bool(config.OVERSEAS_DESC.search(job.description or ""))


_VAGUE_LOCATION = {"", "philippines", "ph", "remote", "luzon", "various locations", "multiple locations"}


def _vague(location: str) -> bool:
    return location.lower().replace(",", " ").split() == [] or location.strip().lower() in _VAGUE_LOCATION


def prefilter_reason(job: Job) -> str:
    """Cheap checks using only what a search result already gives (title + location).
    Runs BEFORE any slow detail request. '' means: worth fetching the full description."""
    roles = match_roles(job.title)
    if not roles:
        return "not a target role"
    if config.WRONG_DISCIPLINE.search(job.title):
        return "other engineering discipline"
    if config.SENIOR_TITLE.search(job.title):
        return "senior / too much experience required"
    if config.OVERSEAS.search(f"{job.title} {job.location}"):
        return "overseas"
    if not area_of(job.location, job.address) and not _vague(job.location):
        return "outside Metro Manila & nearby"
    return ""


def classify(job: Job) -> Job:
    """Fill roles / resume / area and set hidden_reason ('' means the job is shown)."""
    job.roles = match_roles(job.title)
    job.resume = config.ROLES[job.roles[0]]["resume"] if job.roles else ""
    job.area = area_of(job.location, job.address)
    if not job.area and _vague(job.location):
        # e.g. LinkedIn just says "Philippines": look for the city in the first part of the ad.
        job.area = area_of(job.description[:1500])

    pre = prefilter_reason(job)
    if pre and pre != "outside Metro Manila & nearby":
        job.hidden_reason = pre
    elif is_male_restricted(f"{job.title}\n{job.description}"):
        job.hidden_reason = "male only / male preferred"
    elif is_overseas(job):
        job.hidden_reason = "overseas"
    elif is_senior(job.title, job.description):
        job.hidden_reason = "senior / too much experience required"
    elif not job.area:
        job.hidden_reason = "outside Metro Manila & nearby"
    else:
        job.hidden_reason = ""
    return job
