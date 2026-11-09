"""Checks for the male-only filter, seniority, role matching and location. Run: python -m pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from pipeline.filters import area_of, is_male_restricted, is_senior, match_roles  # noqa: E402

MUST_HIDE = [
    "Male only",
    "MALE ONLY applicants",
    "Male applicants only.",
    "Preferably male, 22-35 years old",
    "Preferably Male",
    "Male preferred",
    "Males are preferred for this site position",
    "Male is preferred",
    "Gender: Male",
    "Sex: Male",
    "Must be male",
    "Must be a male",
    "Strictly male",
    "Only male applicants will be entertained",
    "Open for male applicants",
    "Male, 25-40 years old",
    "Site Engineer (Male)",
    "Qualifications:\n- Male\n- Graduate of BSCE",          # handled below via bullet rule? see note
    "Preference: Male",
    "Lalaki, 21-35 taong gulang",
    "We prioritize male candidates",
]
MUST_KEEP = [
    "Male or female",
    "Male/Female, 21-35 years old",
    "Open to male and female applicants",
    "Males and females are welcome",
    "Female only",
    "Female applicants preferred",
    "Preferably female",
    "Gender: Female",
    "Any gender",
    "Regardless of gender",
    "Lalaki o babae",
    "Must be a licensed civil engineer",
    "We are an equal opportunity employer",
    "The female-led team manages construction",
    "M/F, at least 1 year of experience",
]


@pytest.mark.parametrize("text", [t for t in MUST_HIDE if "\n- Male\n" not in t])
def test_male_restricted_hidden(text):
    assert is_male_restricted(text), text


@pytest.mark.parametrize("text", MUST_KEEP)
def test_inclusive_or_female_kept(text):
    assert not is_male_restricted(text), text


def test_bullet_male_line():
    assert is_male_restricted("Qualifications:\n- Male\n- Graduate of BSCE")


@pytest.mark.parametrize("title,roles", [
    ("Junior Site Engineer", ["Site Engineer"]),
    ("Civil Site Engineer", ["Site Engineer"]),
    ("Quantity Surveyor", ["Assistant Quantity Surveyor"]),
    ("Assistant QS", ["Assistant Quantity Surveyor"]),
    ("Cost Estimator", ["Cost Estimator"]),
    ("Office Engineer", ["Office Engineer"]),
    ("Project Engineer (Civil)", ["Project Engineer"]),
    ("Cost Control Engineer", ["Cost Control Engineer"]),
    ("Civil Engineer", ["Civil Engineer (general)"]),
    ("Customer Service Representative", []),
])
def test_roles(title, roles):
    assert match_roles(title) == roles


def test_senior():
    assert is_senior("Senior Site Engineer", "")
    assert is_senior("Site Engineer", "At least 5 years of relevant experience")
    assert not is_senior("Site Engineer", "At least 1 year of experience; fresh graduates welcome")
    assert not is_senior("Site Engineer", "Structural: at least 5 years experience. Site: 2 years experience")
    assert not is_senior("Junior Site Engineer", "")


def test_area():
    assert area_of("Taguig City, Metro Manila") == "Metro Manila"
    assert area_of("Bacoor, Cavite") == "Cavite"
    assert area_of("Cebu City, Cebu") == ""


# ---------------- pre-filter (runs before any slow detail request) ----------------
from pipeline.filters import classify, prefilter_reason  # noqa: E402
from pipeline.model import Job  # noqa: E402


def _job(title, location="Taguig City, Metro Manila", description=""):
    return Job(platform="X", platform_id="1", title=title, company="C", url="u",
               location=location, description=description)


@pytest.mark.parametrize("title,location,reason", [
    ("Site Engineer", "Taguig City, Metro Manila", ""),
    ("Site Engineer", "Philippines", ""),                       # vague → decide after description
    ("Senior Site Engineer", "Makati", "senior / too much experience required"),
    ("Electrical Site Engineer", "Makati", "other engineering discipline"),
    ("Site Engineer", "Cebu City, Cebu", "outside Metro Manila & nearby"),
    ("Site Engineer - Saudi Arabia", "Makati", "overseas"),
    ("Accountant", "Makati", "not a target role"),
])
def test_prefilter(title, location, reason):
    assert prefilter_reason(_job(title, location)) == reason


def test_classify_male_after_description():
    j = classify(_job("Site Engineer", description="Qualifications: Preferably male, 22-30 years old"))
    assert j.hidden_reason == "male only / male preferred"


def test_classify_vague_location_uses_description():
    j = classify(_job("Site Engineer", "Philippines", "Our project site is in Bacoor, Cavite."))
    assert j.area == "Cavite" and j.hidden_reason == ""
