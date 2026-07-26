"""Paths, environment loading, and default role matching."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_FILE = ROOT / "companies.json"
STATE_FILE = ROOT / "state" / "state.json"

# A job title must contain at least one of these to count as a SWE role.
ROLE_TERMS = [
    "software",
    "developer",
    "swe",
    "frontend",
    "front end",
    "front-end",
    "backend",
    "back end",
    "back-end",
    "full stack",
    "full-stack",
    "fullstack",
    "mobile engineer",
    "ios engineer",
    "android engineer",
    "devops",
    "site reliability",
    "sre",
    "platform engineer",
    "infrastructure engineer",
    "data engineer",
    "machine learning",
    "ml engineer",
    "ai engineer",
    "security engineer",
    "cloud engineer",
    "web engineer",
    "qa engineer",
    "test engineer",
]

# Titles containing any of these are dropped even if a role term matched.
ROLE_EXCLUDE_TERMS = [
    "mechanical",
    "electrical",
    "civil engineer",
    "recruiter",
    "sales",
]


def load_dotenv() -> None:
    """Load KEY=VALUE lines from a .env file in the project root, if present.

    Existing environment variables win, so CI secrets are never overridden.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_companies() -> dict[str, list[str]]:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def is_swe_title(title: str) -> bool:
    t = title.lower()
    if any(term in t for term in ROLE_EXCLUDE_TERMS):
        return False
    return any(term in t for term in ROLE_TERMS)
