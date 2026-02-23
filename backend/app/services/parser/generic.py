"""Generic regex parser for ATS systems: Workday, Lever, Greenhouse, and others."""
import re

from app.services.parser.base import ParseResult

# ATS sender domains → platform label stays "direct"
_ATS_DOMAINS = {
    "workday.com": "Workday",
    "lever.co": "Lever",
    "greenhouse.io": "Greenhouse",
    "ashbyhq.com": "Ashby",
    "smartrecruiters.com": "SmartRecruiters",
    "taleo.net": "Taleo",
    "icims.com": "iCIMS",
}

# ── Role extraction ────────────────────────────────────────────────────────────

# "applying to the [Role] position at [Company]" (most specific — checked first)
_BODY_APPLYING_TO = re.compile(
    r"applying\s+to\s+(?:the\s+)?(.{1,120}?)\s+position\s+at\s+(\S.{1,80}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "applying to our/the [Role] position" (no company after)
_APPLYING_OUR_ROLE = re.compile(
    r"applying\s+to\s+(?:our\s+|the\s+)?(.{1,100}?)\s+position(?:\s|$|\.)",
    re.IGNORECASE,
)

# "applying for/applied for [Role] at [Company]"
_ROLE_COMPANY_1 = re.compile(
    r"(?:applying\s+for\s+|applied\s+for\s+)(?:the\s+)?(.{1,100}?)\s+at\s+(.{1,100}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "applying for the position of [Role]"
_POSITION_OF_ROLE = re.compile(
    r"(?:applying\s+for\s+)?the\s+position\s+of\s+(.{1,120}?)(?:,|\.|\n|at\s|$)",
    re.IGNORECASE,
)

# "your interest in the [Role] position"
_INTEREST_IN_ROLE = re.compile(
    r"interest\s+in\s+(?:the\s+)(.{1,120}?)\s+position",
    re.IGNORECASE,
)

# "your application for [Role]," — stops at comma to avoid long matches
_APPLICATION_FOR_ROLE = re.compile(
    r"application\s+for\s+(?:the\s+)?(.{1,120}?)(?:,|\.|$)",
    re.IGNORECASE,
)

# "[Role] position at [Company]" — generic positional match
_ROLE_POSITION_AT = re.compile(
    r"^(.{2,100}?)\s+position\s+at\s+(\S.{1,80}?)(?:\.|,|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)

# "Application for: Senior Designer | Company Name"
_ROLE_COMPANY_2 = re.compile(
    r"(?:Application\s+for[:\s]+|Position[:\s]+)(.{1,100}?)(?:\s*\|\s*|\s+at\s+)(.{1,100}?)(?:\n|$)",
    re.IGNORECASE,
)

# Labelled: "Job Title: Senior Engineer" or "Position: PM"
_JOB_TITLE_LABEL = re.compile(
    r"(?:Job\s+Title|Position|Role)[:\s]+(.{1,120}?)(?:\n|$)",
    re.IGNORECASE,
)

# ── Company extraction ─────────────────────────────────────────────────────────

# "we at [Company] hope..." / "we at [Company],"
_WE_AT_COMPANY = re.compile(
    r"\bwe\s+at\s+([A-Z][A-Za-z0-9&\s\.]{2,60}?)(?:\s+hope|\s+are|\s+want|\s+look|,|\.|$)",
    re.IGNORECASE,
)

# "position with [Company]" — stops at punctuation
_POSITION_WITH_COMPANY = re.compile(
    r"position\s+with\s+([A-Z][A-Za-z0-9&\s\.\-]{2,80}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "interest in [Company Inc.]." — company starts with capital, NOT followed by "position"
# Guards against matching "interest in the [Role] position" by requiring >= 5 chars before terminator
_INTEREST_IN_COMPANY = re.compile(
    r"interest\s+in\s+([A-Z][A-Za-z0-9&\s\.\-]{4,60}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# Labelled: "Company: Google" or "Employer: Google"
_COMPANY_LABEL = re.compile(
    r"(?:Company|Employer|Organization|Hiring\s+Company)[:\s]+([A-Z][A-Za-z0-9&\s,\.]{1,60})",
    re.IGNORECASE,
)

# ── Location & Salary ─────────────────────────────────────────────────────────

# Location: labelled "Location: Remote" or "Location: Seattle, WA" (colon required)
_BODY_LOCATION_LABEL = re.compile(
    r"Location:\s*([^\n,\.]{3,80})",
    re.IGNORECASE,
)

# Work-mode keywords only — avoids matching generic English words
_LOCATION_KEYWORDS = re.compile(
    r"\b(Remote|Hybrid|On-?site|Onsite)\b",
    re.IGNORECASE,
)

# City + 2-letter state abbreviation (e.g. "Seattle, WA")
_LOCATION_CITY_STATE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})\b",
)

# Fallback: the word "remote" appearing anywhere in body/subject
_REMOTE_ANYWHERE = re.compile(r"\bremote\b", re.IGNORECASE)

# "(Remote)" or "- Remote" appended to a job title
_LOCATION_IN_TITLE = re.compile(
    r"\s*[\(\-]\s*(Remote|Hybrid|On-?site)\s*\)?",
    re.IGNORECASE,
)

_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)


def _strip_location_from_title(title: str) -> tuple[str, str | None]:
    """
    If job title contains "(Remote)", "- Remote", etc., strip it and return
    (cleaned_title, location_string).
    """
    m = _LOCATION_IN_TITLE.search(title)
    if m:
        location = m.group(1).strip()
        cleaned = title[:m.start()].strip()
        return cleaned, location
    return title, None


def parse(sender: str, subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="direct")

    # 1. Most specific: "applying to the [Role] position at [Company]"
    m = _BODY_APPLYING_TO.search(body)
    if m:
        result.job_title = m.group(1).strip()
        result.company_name = m.group(2).strip()

    # 2. "applying for [Role] at [Company]"
    if not result.job_title:
        m = _ROLE_COMPANY_1.search(body) or _ROLE_COMPANY_1.search(subject)
        if m:
            result.job_title = m.group(1).strip()
            result.company_name = m.group(2).strip()

    # 3. "Application for: Role | Company" or subject equivalent
    if not result.job_title:
        m = _ROLE_COMPANY_2.search(body) or _ROLE_COMPANY_2.search(subject)
        if m:
            result.job_title = m.group(1).strip()
            result.company_name = m.group(2).strip()

    # 4. "[Role] position at [Company]" — any line
    if not result.job_title:
        m = _ROLE_POSITION_AT.search(body) or _ROLE_POSITION_AT.search(subject)
        if m:
            result.job_title = m.group(1).strip()
            if not result.company_name:
                result.company_name = m.group(2).strip()

    # 5. "interest in the [Role] position"
    if not result.job_title:
        m = _INTEREST_IN_ROLE.search(body) or _INTEREST_IN_ROLE.search(subject)
        if m:
            result.job_title = m.group(1).strip()

    # 6. "applying to our [Role] position"
    if not result.job_title:
        m = _APPLYING_OUR_ROLE.search(body) or _APPLYING_OUR_ROLE.search(subject)
        if m:
            result.job_title = m.group(1).strip()

    # 7. "position of [Role]"
    if not result.job_title:
        m = _POSITION_OF_ROLE.search(body) or _POSITION_OF_ROLE.search(subject)
        if m:
            result.job_title = m.group(1).strip()

    # 8. "application for [Role],"
    if not result.job_title:
        m = _APPLICATION_FOR_ROLE.search(body) or _APPLICATION_FOR_ROLE.search(subject)
        if m:
            candidate = m.group(1).strip()
            # Reject sentence fragments masquerading as job titles.
            # Real titles are short (≤7 words) and don't start with pronouns/fillers.
            word_count = len(candidate.split())
            if (word_count <= 7 and
                    not re.match(r'^(?:this|our|your|the\s+(?:role|search|position|company))\b',
                                 candidate, re.IGNORECASE)):
                result.job_title = candidate

    # 9. Labelled: "Job Title: ..."
    if not result.job_title:
        m = _JOB_TITLE_LABEL.search(body)
        if m:
            result.job_title = m.group(1).strip()

    # Strip location suffix from job title (e.g. "Engineer (Remote)" → title="Engineer", loc="Remote")
    if result.job_title:
        result.job_title, extracted_loc = _strip_location_from_title(result.job_title)
        if extracted_loc and not result.location:
            result.location = extracted_loc

    # ── Company ────────────────────────────────────────────────────────────────

    # "we at [Company]"
    if not result.company_name:
        m = _WE_AT_COMPANY.search(body) or _WE_AT_COMPANY.search(subject)
        if m:
            result.company_name = m.group(1).strip()

    # "position with [Company]"
    if not result.company_name:
        m = _POSITION_WITH_COMPANY.search(body)
        if m:
            result.company_name = m.group(1).strip()

    # "interest in [Company Inc.]"
    if not result.company_name:
        m = _INTEREST_IN_COMPANY.search(body)
        if m:
            name = m.group(1).strip()
            # Filter out phrases that are role descriptions, not company names
            if "position" not in name.lower() and "role" not in name.lower():
                result.company_name = name

    # Labelled: "Company: Google"
    if not result.company_name:
        m = _COMPANY_LABEL.search(body)
        if m:
            result.company_name = m.group(1).strip()

    # ── Location ───────────────────────────────────────────────────────────────
    # 1. Labelled "Location: Remote" or "Location: Seattle, WA" (colon required)
    if not result.location:
        m = _BODY_LOCATION_LABEL.search(body)
        if m:
            result.location = m.group(1).strip()
    # 2. Work-mode keywords: Remote / Hybrid / On-site
    if not result.location:
        m = _LOCATION_KEYWORDS.search(body) or _LOCATION_KEYWORDS.search(subject)
        if m:
            result.location = m.group(1).strip().capitalize()
    # 3. City + state abbreviation (e.g. "Seattle, WA")
    if not result.location:
        m = _LOCATION_CITY_STATE.search(body) or _LOCATION_CITY_STATE.search(subject)
        if m:
            result.location = m.group(1).strip()
    # 4. Final fallback: if "remote" appears anywhere in body or subject, use it
    if not result.location:
        if _REMOTE_ANYWHERE.search(body) or _REMOTE_ANYWHERE.search(subject):
            result.location = "Remote"

    # ── Salary ─────────────────────────────────────────────────────────────────
    m = _SALARY.search(body) or _SALARY.search(subject)
    if m:
        result.salary_range = m.group(0).strip()

    return result
