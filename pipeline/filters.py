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


# ---------------------------------------------------------------------------------------
# Experience requirement. She has a few months of experience, so an ad is only kept when it
# is open to fresh graduates / entry level, asks for less than 1 year, or says nothing.
# ---------------------------------------------------------------------------------------
_NUM_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split())}
_NUM_WORD_RE = re.compile(r"\b(" + "|".join(_NUM_WORDS) + r")\b", re.I)
_DASHES = re.compile(r"[‐‑‒–—―−~�]")
# experience / experiences / experienced / common typos (experince, expereince, experiance) / exp.
_EXP_WORD = re.compile(r"\b(exp[ei]r\w{0,3}n[cs]e[sd]?|experienced|exp\.?|worked|working\s+in|track\s+record)\b", re.I)
_NOT_EXP = re.compile(r"\b(years?\s*old|of\s*age|age\s*\d|warranty|in\s*business|in\s*the\s*industry\s*for|"
                      r"established|founded|serving|company\s*with|since\s*\d{4}|"
                      r"(we|our\s*(company|firm|team|group)|the\s*company|company)\s*(has|have|brings?)|"
                      r"backed\s*by|over\s*the\s*(past|last))\b", re.I)
_UNIT = r"(years?|yrs?\.?|y\.?o\.?e|months?|mos?\.?)"
# "1-2 years", "1 to 2 years", "3 - 4 yrs"
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*['’]?\s*" + _UNIT, re.I)
# "2 years", "2+ years", "2-years'", "5 years and up", "6 months"
_SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*-?\s*['’]?\s*" + _UNIT, re.I)
# Strong: the ad itself invites people with no / little experience. Always wins.
FRESH_OK = re.compile(
    r"\b(fresh\s*(graduates?|grads?)|new\s*(graduates?|grads?)|recent\s*graduates?|entry[\s-]*level|"
    r"graduating\s*students?|no\s*(work\s*|prior\s*)?experience\s*(is\s*)?(required|needed|necessary)|"
    r"without\s*(work\s*)?experience|with\s*or\s*without\s*(work\s*)?experience|"
    r"experience\s*is\s*not\s*(required|necessary)|"
    r"open\s*to\s*(fresh|new)|trainee)\b",
    re.I,
)
# Weak: "experience is a plus / an advantage". Only counts when no years are demanded
# (e.g. "Minimum 3 years experience. SAP experience is a plus" must still be hidden).
EXP_OPTIONAL = re.compile(
    r"\bexperience\s*(is|would\s*be)\s*(optional|a\s*plus|an\s*advantage|advantageous|preferred\s*but\s*not\s*required)\b",
    re.I,
)


# Asks for experience but gives no number ("proven experience in…", "with experience in…").
SOME_EXP = re.compile(
    r"(\b(proven|solid|extensive|progressive|substantial|strong|relevant|related|must\s*have|should\s*have|"
    r"preferably\s*with|with|minimum|at\s*least)\b[^\n.]{0,30}\bexp[ei]r\w*n[cs]e\b"
    r"|^\W*experienced?\s+(in|with|as)\b)",
    re.I | re.M,
)


def _normalize(text: str) -> str:
    t = _DASHES.sub("-", (text or "").replace("**", "").replace("__", ""))
    t = _NUM_WORD_RE.sub(lambda m: _NUM_WORDS[m.group(1).lower()], t)
    t = re.sub(r"(\d+)\s*\(\s*\1\s*\)", r"\1", t)          # "two (2) years" → "2 years"
    return t


def required_years(text: str) -> list[float]:
    """Minimum years asked for in each experience statement of the ad (one value per statement)."""
    out = []
    for line in re.split(r"[\n;•]|\.(?=\s|$)", _normalize(text)):
        if not _EXP_WORD.search(line) or _NOT_EXP.search(line):
            continue
        found = []
        for m in _RANGE.finditer(line):
            lo = float(m.group(1))
            found.append(lo / 12 if m.group(3).lower().startswith("m") else lo)
        if not found:
            for m in _SINGLE.finditer(line):
                n = float(m.group(1))
                found.append(n / 12 if m.group(2).lower().startswith("m") else n)
        found = [f for f in found if 0 <= f <= 15]          # ignore "40 years in business" etc.
        if found:
            out.append(min(found))
    return out


def experience_label(title: str, description: str) -> tuple[str, bool]:
    """→ (label shown on the card, too_much). too_much=True means hide the job."""
    if FRESH_OK.search(f"{title}\n{description}"):
        return "Fresh graduates OK", False
    years = required_years(description)
    if not years:
        if EXP_OPTIONAL.search(description or ""):
            return "Fresh graduates OK", False
        if SOME_EXP.search(description or ""):
            return "Some experience preferred", False
        return "Experience not mentioned", False
    need = min(years)                       # several positions in one ad → the easiest one counts
    if need < config.MAX_EXPERIENCE_YEARS:
        return ("Less than 1 year" if need > 0 else "No experience needed"), False
    shown = f"{need:g}+ years"
    return f"Needs {shown}", True


def is_senior(title: str, description: str) -> bool:
    if config.SENIOR_TITLE.search(title):
        return True
    return experience_label(title, description)[1]


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
    if re.search(r"\b(intern|interns|internship|ojt|on[\s-]*the[\s-]*job\s*train)", job.title, re.I):
        return "internship"
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

    job.experience, too_much = experience_label(job.title, job.description)
    pre = prefilter_reason(job)
    if pre and pre != "outside Metro Manila & nearby":
        job.hidden_reason = pre
    elif is_male_restricted(f"{job.title}\n{job.description}"):
        job.hidden_reason = "male only / male preferred"
    elif is_overseas(job):
        job.hidden_reason = "overseas"
    elif too_much:
        job.hidden_reason = "senior / too much experience required"
    elif not job.area:
        job.hidden_reason = "outside Metro Manila & nearby"
    else:
        job.hidden_reason = ""
    return job
