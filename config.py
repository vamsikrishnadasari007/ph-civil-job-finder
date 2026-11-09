"""All tunable settings in one place: roles, search keywords, locations, filter patterns."""
import re

# How far back to collect (the UI then narrows to 1 day / 3 days / ... / 2 weeks).
DAYS_BACK = 14
# Jobs older than this are dropped from the stored data entirely.
KEEP_DAYS = 21

# --------------------------------------------------------------------------------------
# Roles. `title` regexes decide which role(s) a job belongs to (matched on the job TITLE).
# `resume` is the file she should send for that role.
# --------------------------------------------------------------------------------------
ROLES = {
    "Site Engineer": dict(
        title=[r"\bsite\s*engineer", r"\bfield\s*engineer", r"\bconstruction\s*engineer",
               r"\bsite\s*civil\s*engineer", r"\bcivil\s*site\s*engineer", r"\bproject\s*site\s*engineer"],
        resume="Site Engineer",
    ),
    "Cost Estimator": dict(
        title=[r"\bestimator\b", r"\bestimation\s*engineer", r"\bcost\s*estimat", r"\bestimating\s*engineer"],
        resume="Cost Estimator",
    ),
    "Assistant Quantity Surveyor": dict(
        title=[r"\bquantity\s*surveyor", r"\bquantity\s*surveying", r"\bquantity\s*engineer", r"\bQS\b"],
        resume="Assistant Quantity Surveyor",
    ),
    "Office Engineer": dict(
        title=[r"\boffice\s*engineer", r"\bdocument\s*control", r"\bproject\s*documentation",
               r"\bengineering\s*assistant", r"\btechnical\s*office"],
        resume="Office Engineer",
    ),
    "Project Engineer": dict(
        title=[r"\bproject\s*engineer"],
        resume="Project Engineer",
    ),
    "Cost Control Engineer": dict(
        title=[r"\bcost\s*control", r"\bcost\s*engineer", r"\bbilling\s*engineer", r"\bcost\s*and\s*billing"],
        resume="Cost Control Engineer",
    ),
    "Civil Engineer (general)": dict(
        title=[r"\bcivil\s*engineer", r"\bjunior\s*engineer\b", r"\bstructural\s*engineer"],
        resume="Site Engineer",
    ),
}

# Keywords sent to the job sites' own search boxes (broad; titles are re-checked locally).
SEARCH_KEYWORDS = [
    "site engineer", "civil engineer", "field engineer", "construction engineer",
    "estimator", "cost estimator", "quantity surveyor", "office engineer", "document controller",
    "project engineer", "cost control engineer", "billing engineer", "junior engineer",
]
# Smaller set for the sites that rate-limit hard (LinkedIn, Indeed).
SEARCH_KEYWORDS_LIGHT = [
    "site engineer", "civil engineer", "estimator", "quantity surveyor",
    "office engineer", "project engineer", "cost control engineer",
]

# Titles in another engineering discipline / IT are not for her (she is a Civil Engineer).
WRONG_DISCIPLINE = re.compile(
    r"\b(electrical|electronics?|mechanical|software|it|network|devops|reliability|sre|chemical|process|"
    r"industrial|mepf?|plumbing|sanitary|telecoms?|hvac|fdas|instrumentation|systems?|cloud|qa|"
    r"security|automation|maintenance|manufacturing|production|biomedical|geodetic|marine|petroleum|"
    r"mining|solar|fire\s*protection|aircon|elevator|piping|welding|automotive|computer|web|sales|"
    r"accounting|finance|insurance|medical|pharma|"
    r"pre-?sales|application|integration|support|firmware|embedded|ai|ml|machine\s*learning)\b",
    re.I,
)

# --------------------------------------------------------------------------------------
# Seniority (she is entry level) — hide these.
# --------------------------------------------------------------------------------------
SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|manager|head|lead|principal|director|chief|superintendent|supervisor|"
    r"vice\s*president|vp|officer[-\s]in[-\s]charge|oic|consultant|specialist\s*iii)\b",
    re.I,
)
# A description that ONLY asks for >= this many years of experience is treated as senior.
SENIOR_MIN_YEARS = 3

# --------------------------------------------------------------------------------------
# Locations: Metro Manila + nearby provinces. Overseas is skipped.
# --------------------------------------------------------------------------------------
AREAS = {
    "Metro Manila": [
        "metro manila", "ncr", "national capital", "manila", "taguig", "makati", "pasig", "quezon city",
        "mandaluyong", "pasay", "paranaque", "parañaque", "las pinas", "las piñas", "muntinlupa",
        "alabang", "marikina", "san juan", "caloocan", "valenzuela", "malabon", "navotas", "pateros",
        "bgc", "bonifacio global", "ortigas", "fort bonifacio",
    ],
    "Cavite": ["cavite", "bacoor", "imus", "dasmarinas", "dasmariñas", "general trias", "kawit", "silang",
               "tagaytay", "carmona", "rosario", "trece martires", "gma"],
    "Laguna": ["laguna", "santa rosa", "sta. rosa", "sta rosa", "binan", "biñan", "calamba", "san pedro",
               "cabuyao", "los banos", "los baños", "san pablo"],
    "Rizal": ["rizal", "antipolo", "cainta", "taytay", "binangonan", "san mateo", "rodriguez", "montalban",
              "angono"],
    "Bulacan": ["bulacan", "malolos", "meycauayan", "san jose del monte", "marilao", "bocaue", "balagtas",
                "baliuag", "baliwag", "guiguinto", "plaridel", "sta. maria", "santa maria"],
    "Pampanga": ["pampanga", "san fernando", "angeles", "clark", "mabalacat"],
    "Batangas": ["batangas", "lipa", "tanauan", "sto. tomas", "santo tomas"],
}
# Search areas sent to the job sites.
SEARCH_LOCATIONS = ["Metro Manila", "Cavite", "Laguna", "Rizal", "Bulacan", "Pampanga", "Batangas"]

OVERSEAS = re.compile(
    r"\b(overseas|abroad|ofw|saudi|ksa|riyadh|jeddah|uae|dubai|abu\s*dhabi|qatar|doha|kuwait|oman|bahrain|"
    r"middle\s*east|singapore|malaysia|hong\s*kong|taiwan|japan|korea|australia|new\s*zealand|canada|"
    r"poea|dmw\s*licen[cs]e|deployment\s*abroad)\b",
    re.I,
)
# For descriptions we only use phrases that clearly mean the job itself is abroad.
OVERSEAS_DESC = re.compile(
    r"\b(work(ing)?\s*abroad|overseas\s*(employment|deployment|job|position)|deploy(ed|ment)\s*(to|in)\s*"
    r"(saudi|ksa|uae|dubai|qatar|kuwait|oman|bahrain|the\s*middle\s*east)|job\s*site\s*:\s*(saudi|ksa|uae|"
    r"dubai|qatar|kuwait))\b",
    re.I,
)

# --------------------------------------------------------------------------------------
# Gender filter: hide MALE-only / MALE-preferred ads. Female-only ads are kept.
# --------------------------------------------------------------------------------------
# Inclusive phrases are removed from the text first, so they can never trigger a match.
GENDER_INCLUSIVE = re.compile(
    r"\b(males?\s*(/|or|and|&|,)\s*females?|females?\s*(/|or|and|&|,)\s*males?|both\s*(genders|sexes)|"
    r"(any|all|regardless\s*of|open\s*to\s*all)\s*genders?|m\s*/\s*f|f\s*/\s*m|"
    r"lalaki\s*(o|at)\s*babae|babae\s*(o|at)\s*lalaki)\b",
    re.I,
)
MALE_ONLY = [
    r"\bmales?\s*(applicants?|candidates?)?\s*only\b",                      # male only / male applicants only
    r"\b(only|strictly|exclusively)\s*(for\s*)?males?\b",                     # only male / strictly male
    r"\bfor\s*males?\b",                                                      # for male
    r"\bmales?\s*(are\s*|is\s*)?(preferred|preferably|prioriti[sz]ed|priority|preference)\b",  # male preferred
    r"\bprefer(ably|red|ence)?\s*(is\s*|to\s*be\s*|for\s*|:\s*)?(a\s*)?males?\b",               # preferably male
    r"\bmust\s*be\s*(a\s*)?males?\b",                                         # must be male
    r"\b(gender|sex)\s*[:\-–]?\s*(preferably\s*)?males?\b",                   # gender: male
    r"\bmales?\s*,?\s*(age\s*)?\d{2}\s*(-|–|to)\s*\d{2}\b",                   # male, 25-35 years old
    r"\bmales?\s*(applicants?|candidates?)\b",                                # male applicants ...
    r"\(\s*males?\s*\)",                                                      # (Male) in a title
    r"(?m)^\s*[-•*·▪●]?\s*males?\s*[,;.]?\s*$",                               # a bullet line that is just "Male"
    r"\b(lalaki|lalake)\b",                                                   # Filipino: male
]
MALE_ONLY_RE = [re.compile(p, re.I) for p in MALE_ONLY]

# --------------------------------------------------------------------------------------
# Links shown on the site for places that cannot be scraped safely.
# --------------------------------------------------------------------------------------
EXTRA_LINKS = [
    ("PhilJobNet (DOLE)", "https://philjobnet.gov.ph/"),
    ("Bossjob PH: Civil Engineer", "https://bossjob.ph/en-us/jobs-hiring/civil-engineer-jobs"),
    ("Facebook: Civil Engineering Jobs PH (search groups)", "https://www.facebook.com/search/groups/?q=civil%20engineering%20jobs%20philippines"),
    ("Facebook: Site Engineer Hiring PH (search posts)", "https://www.facebook.com/search/posts/?q=hiring%20site%20engineer%20manila"),
    ("Reddit r/phcareers", "https://www.reddit.com/r/phcareers/search/?q=civil%20engineer&sort=new"),
    ("Reddit r/PHJobs", "https://www.reddit.com/r/PHJobs/search/?q=engineer&sort=new"),
    ("foundit PH: Civil Engineer", "https://www.foundit.com.ph/srp/results?query=civil%20engineer&locations=Manila"),
    ("Google Jobs: Site Engineer Metro Manila", "https://www.google.com/search?q=site+engineer+jobs+metro+manila&ibp=htl;jobs"),
    ("Google Jobs: Quantity Surveyor Metro Manila", "https://www.google.com/search?q=quantity+surveyor+jobs+metro+manila&ibp=htl;jobs"),
]
