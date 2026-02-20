"""Regex-based parser for Indeed application confirmation emails.

Observed sender domains: indeedapply@indeed.com, no-reply@indeed.com,
                         jobs-noreply@indeed.com, <company>@indeed.com

Observed subject formats:
  1. "Indeed Application: UI/UX Designer"
  2. "Your application to Google was sent"
  3. "New Message from Topflight Talent - Associate Product Manager"
  4. "Application submitted to Google"

Standard body format (most common):
  Application submitted

  UI/UX Designer
  Qredible Inc - Remote

  The following items were sent to Qredible Inc. Good luck!
"""
import re

from app.services.parser.base import ParseResult

# Format 1: "Indeed Application: [Role]"
_SUBJECT_INDEED_APP = re.compile(
    r"Indeed Application:\s*(.{1,120}?)(?:\s*[\(\[]|$)",
    re.IGNORECASE,
)

# Format 2: "Your application to [Company] was sent/submitted"
_SUBJECT_COMPANY = re.compile(
    r"application\s+(?:to|submitted\s+to)\s+(.+?)\s+(?:was|has been|received)",
    re.IGNORECASE,
)

# Format 3: "New Message from [Company] - [Role]"
_SUBJECT_MSG_FROM = re.compile(
    r"New Message from\s+(.+?)\s+-\s+(.{1,120}?)$",
    re.IGNORECASE,
)

# Body: "Job title" or "Position: Senior Engineer"
_BODY_ROLE_LABEL = re.compile(
    r"(?:Job\s+[Tt]itle|Position)[:\s]+([^\n]{1,120})",
)

# Body/snippet: "Thank you for applying to the [Role] position at [Company]"
# Company may start with a digit (e.g. "1TO5.AI LLC"), so use \S instead of [A-Z]
_BODY_APPLYING_TO = re.compile(
    r"applying\s+to\s+(?:the\s+)?(.{1,120}?)\s+position\s+at\s+(\S.{1,80}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# Body: "You applied for [Role]" / "applied for the position of [Role]"
_BODY_ROLE = re.compile(
    r"(?:applied\s+for\s+(?:the\s+)?(?:position\s+of\s+)?|position:\s*)(.{1,120}?)(?:\n|at\s|\.|$)",
    re.IGNORECASE,
)

# Standard Indeed body: "Qredible Inc - Remote" (company name - location)
# Works on both multi-line and HTML-stripped single-line bodies.
# Anchored to end with a word boundary / space to avoid mid-sentence matches.
_BODY_COMPANY_DASH_LOCATION = re.compile(
    r"([A-Z][A-Za-z0-9&\s\.]{2,60}?)\s*[-–]\s*(Remote|Hybrid|On-?site)(?=\s|\.|,|$)",
    re.IGNORECASE,
)

# "The following items were sent to Qredible Inc. Good luck!"
# Very reliable company extractor — appears in every standard Indeed email
_BODY_ITEMS_SENT_TO = re.compile(
    r"(?:items\s+were\s+sent\s+to|submitted\s+to)\s+([A-Z][A-Za-z0-9&\s\.\,\-]{2,80}?)\.",
    re.IGNORECASE,
)

# Body: "Company: Google" or "Employer: Google"
_BODY_COMPANY_LABEL = re.compile(
    r"(?:Company|Employer)[:\s]+([A-Z][A-Za-z0-9&\s,\.]{1,80}?)(?:\n|$|\.|,)",
)

# Body: "at Google" (last resort)
_BODY_AT_COMPANY = re.compile(
    r"\bat\s+([A-Z][A-Za-z0-9&\s,\.]{1,60}?)(?:\n|$|\.|,)",
    re.MULTILINE,
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

_REMOTE_ANYWHERE = re.compile(r"\bremote\b", re.IGNORECASE)

_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)

# "(Remote)" or "- Remote" suffix in a job title
_LOCATION_IN_TITLE = re.compile(
    r"\s*[\(\-]\s*(Remote|Hybrid|On-?site)\s*\)?",
    re.IGNORECASE,
)


def _strip_location_from_title(title: str) -> tuple[str, str | None]:
    m = _LOCATION_IN_TITLE.search(title)
    if m:
        return title[:m.start()].strip(), m.group(1).strip()
    return title, None


def parse(subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="indeed")

    # --- Subject extraction ---

    # Format 3: "New Message from [Company] - [Role]"
    m = _SUBJECT_MSG_FROM.search(subject)
    if m:
        result.company_name = m.group(1).strip()
        result.job_title = m.group(2).strip()

    # Format 1: "Indeed Application: [Role]"
    if not result.job_title:
        m = _SUBJECT_INDEED_APP.search(subject)
        if m:
            result.job_title = m.group(1).strip()

    # Format 2: "application to [Company] was sent"
    if not result.company_name:
        m = _SUBJECT_COMPANY.search(subject)
        if m:
            result.company_name = m.group(1).strip()

    # --- Body extraction (fill in what subject didn't give us) ---

    # Priority 1: Standard Indeed format — "Company Name - Remote" on its own line.
    # Gives both company AND location simultaneously.
    if not result.company_name or not result.location:
        m = _BODY_COMPANY_DASH_LOCATION.search(body)
        if m:
            if not result.company_name:
                result.company_name = m.group(1).strip()
            if not result.location:
                result.location = m.group(2).strip().capitalize()

    # Priority 2: "The following items were sent to [Company]. Good luck!"
    # Very reliable — appears in every standard Indeed confirmation.
    if not result.company_name:
        m = _BODY_ITEMS_SENT_TO.search(body)
        if m:
            result.company_name = m.group(1).strip()

    # Priority 3: "applying to the [Role] position at [Company]"
    if not result.job_title or not result.company_name:
        m = _BODY_APPLYING_TO.search(body)
        if m:
            if not result.job_title:
                result.job_title = m.group(1).strip()[:120]
            if not result.company_name:
                result.company_name = m.group(2).strip()

    if not result.job_title:
        m = _BODY_ROLE_LABEL.search(body) or _BODY_ROLE.search(body)
        if m:
            result.job_title = m.group(1).strip()[:120]

    if not result.company_name:
        m = _BODY_COMPANY_LABEL.search(body)
        if m:
            result.company_name = m.group(1).strip()

    if not result.company_name:
        m = _BODY_AT_COMPANY.search(body[:600])
        if m:
            result.company_name = m.group(1).strip()

    # Strip location suffix from job title e.g. "Engineer (Remote)" → loc="Remote"
    if result.job_title:
        result.job_title, extracted_loc = _strip_location_from_title(result.job_title)
        if extracted_loc and not result.location:
            result.location = extracted_loc

    # --- Location & Salary ---
    # Strip out the boilerplate Indeed footer so it doesn't pollute location
    # extraction. The footer always starts with "Indeed - one search."
    body_no_footer = re.split(r"Indeed\s*[-–]\s*one search", body, maxsplit=1)[0]

    # 1. Work-mode keywords: Remote / Hybrid / On-site
    if not result.location:
        m = _LOCATION_KEYWORDS.search(body_no_footer) or _LOCATION_KEYWORDS.search(subject)
        if m:
            result.location = m.group(1).strip().capitalize()
    # 2. City + state abbreviation (e.g. "Seattle, WA")
    if not result.location:
        m = _LOCATION_CITY_STATE.search(body_no_footer) or _LOCATION_CITY_STATE.search(subject)
        if m:
            result.location = m.group(1).strip()
    # 3. Last resort: "remote" anywhere
    if not result.location:
        if _REMOTE_ANYWHERE.search(body) or _REMOTE_ANYWHERE.search(subject):
            result.location = "Remote"

    m = _SALARY.search(body) or _SALARY.search(subject)
    if m:
        result.salary_range = m.group(0).strip()

    return result
