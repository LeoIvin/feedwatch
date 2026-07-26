"""User-adjustable filtering on top of the baseline SWE title match."""

from .ats import Job
from .config import is_swe_title


def matches(job: Job, filters: dict) -> bool:
    if not is_swe_title(job.title):
        return False
    title = job.title.lower()
    location = job.location.lower()

    keywords = [k.lower() for k in filters.get("keywords", [])]
    if keywords and not any(k in title for k in keywords):
        return False

    if filters.get("remote_only") and not job.is_remote:
        return False

    locations = [loc.lower() for loc in filters.get("locations", [])]
    if locations:
        # A remote job is acceptable for any location preference.
        if not job.is_remote and not any(loc in location for loc in locations):
            return False

    return True
