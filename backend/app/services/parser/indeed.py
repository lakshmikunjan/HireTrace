"""Regex-based parser for Indeed application confirmation emails.

Observed sender domains: indeedapply@indeed.com, no-reply@indeed.com,
                         jobs-noreply@indeed.com, <company>@indeed.com

Observed subject formats:
  1. "Indeed Application: UI/UX Designer"
  2. "Your application to Google was sent"
  3. "New Message from Topflight Talent - Associate Product Manager"
  4. "Application submitted to Google"

Standard body format (most common, one item per line after HTML stripping):
  Application submitted

  UI/UX Designer
  Qredible Inc - Remote        ← or "HungerRush - Houston, TX"

  The following items were sent to Qredible Inc. Good luck!
"""
import re

from app.services.parser.base import ParseResult

# ---------------------------------------------------------------------------
# Subject patterns
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Body — role patterns
# ---------------------------------------------------------------------------

# "Job title: Senior Engineer" or "Position: Senior Engineer"
_BODY_ROLE_LABEL = re.compile(
    r"(?:Job\s+[Tt]itle|Position)[:\s]+([^\n]{1,120})",
)

# "Thank you for applying to the [Role] position at [Company]"
_BODY_APPLYING_TO = re.compile(
    r"applying\s+to\s+(?:the\s+)?(.{1,120}?)\s+position\s+at\s+(\S.{1,80}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "applied for [Role]" / "position: [Role]"
_BODY_ROLE = re.compile(
    r"(?:applied\s+for\s+(?:the\s+)?(?:position\s+of\s+)?|position:\s*)(.{1,120}?)(?:\n|at\s|\.|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Body — company patterns
# ---------------------------------------------------------------------------

# Standard Indeed confirmation line: "Company Name - Remote" OR "Company - City, ST"
# MUST be at the start of a line (^ with MULTILINE) so it never spans across
# the job-title line and greedily captures role text as part of the company.
# Char class deliberately excludes '-' (separator) and newlines.
_BODY_COMPANY_DASH_LOCATION = re.compile(
    r"^([A-Z][A-Za-z0-9&' ,\.]{1,60}?)[ \t]*[-–][ \t]*"
    r"(Remote|Hybrid|On-?site|Onsite|[A-Z][A-Za-z \t\.]+,[ \t]*[A-Z]{2})[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# "The following items were sent to Qredible Inc. Good luck!"
# Very reliable — appears in every standard Indeed confirmation.
# Deliberately EXCLUDES "submitted to" which is too broad and matches job descriptions.
_BODY_ITEMS_SENT_TO = re.compile(
    r"items[ \t]+were[ \t]+sent[ \t]+to[ \t]+([A-Z][A-Za-z0-9&' ,\.\-]{2,80}?)\.",
    re.IGNORECASE,
)

# "Company: Google" or "Employer: Google"
_BODY_COMPANY_LABEL = re.compile(
    r"(?:Company|Employer)[ \t]*:[ \t]*([A-Z][A-Za-z0-9&' \t,\.]{1,80}?)(?:\n|$|\.|,)",
)

# "at Google" (last resort, first 600 chars only)
_BODY_AT_COMPANY = re.compile(
    r"\bat[ \t]+([A-Z][A-Za-z0-9&' \t,\.]{1,60}?)(?:\n|$|\.|,)",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Location patterns
# ---------------------------------------------------------------------------

# Work-mode keywords only
_LOCATION_KEYWORDS = re.compile(
    r"\b(Remote|Hybrid|On-?site|Onsite)\b",
    re.IGNORECASE,
)

# City + 2-letter state (e.g. "Seattle, WA").
# Use [ \t]+ (not \s+) to prevent matching across lines.
_LOCATION_CITY_STATE = re.compile(
    r"\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)*,[ \t]*[A-Z]{2})\b",
)

_REMOTE_ANYWHERE = re.compile(r"\bremote\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)

# "(Remote)" or "- Remote" suffix in a job title
_LOCATION_IN_TITLE = re.compile(
    r"\s*[\(\-]\s*(Remote|Hybrid|On-?site)\s*\)?",
    re.IGNORECASE,
)

_WHITESPACE_NORMALIZE = re.compile(r"\s+")


def _clean(s: str | None) -> str | None:
    """Collapse any internal newlines/tabs to a single space and strip."""
    if not s:
        return s
    return _WHITESPACE_NORMALIZE.sub(" ", s).strip()


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
        result.company_name = _clean(m.group(1))
        result.job_title = _clean(m.group(2))

    # Format 1: "Indeed Application: [Role]"
    if not result.job_title:
        m = _SUBJECT_INDEED_APP.search(subject)
        if m:
            result.job_title = _clean(m.group(1))

    # Format 2: "application to [Company] was sent"
    if not result.company_name:
        m = _SUBJECT_COMPANY.search(subject)
        if m:
            result.company_name = _clean(m.group(1))

    # --- Body extraction ---

    # Priority 1: "Company Name - Remote" or "Company Name - City, ST" on its own line.
    # Line-anchored (^...$) so it never captures job-title text in the company group.
    if not result.company_name or not result.location:
        m = _BODY_COMPANY_DASH_LOCATION.search(body)
        if m:
            if not result.company_name:
                result.company_name = _clean(m.group(1))
            if not result.location:
                result.location = _clean(m.group(2))

    # Priority 2: "The following items were sent to [Company]. Good luck!"
    if not result.company_name:
        m = _BODY_ITEMS_SENT_TO.search(body)
        if m:
            result.company_name = _clean(m.group(1))

    # Priority 2.5: subject "Application submitted to Google"
    if not result.company_name:
        m = re.search(
            r"(?:submitted|sent)\s+to\s+([A-Z][A-Za-z0-9&' \.]{2,60}?)(?:\s*$|\.|,)",
            subject, re.IGNORECASE,
        )
        if m:
            result.company_name = _clean(m.group(1))

    # Priority 3: "applying to the [Role] position at [Company]"
    if not result.job_title or not result.company_name:
        m = _BODY_APPLYING_TO.search(body)
        if m:
            if not result.job_title:
                result.job_title = _clean(m.group(1))[:120]
            if not result.company_name:
                result.company_name = _clean(m.group(2))

    if not result.job_title:
        m = _BODY_ROLE_LABEL.search(body) or _BODY_ROLE.search(body)
        if m:
            result.job_title = _clean(m.group(1))[:120]

    if not result.company_name:
        m = _BODY_COMPANY_LABEL.search(body)
        if m:
            result.company_name = _clean(m.group(1))

    if not result.company_name:
        m = _BODY_AT_COMPANY.search(body[:600])
        if m:
            result.company_name = _clean(m.group(1))

    # Strip location suffix from job title e.g. "Engineer (Remote)" → loc="Remote"
    if result.job_title:
        result.job_title, extracted_loc = _strip_location_from_title(result.job_title)
        if extracted_loc and not result.location:
            result.location = extracted_loc

    # --- Location & Salary ---
    body_no_footer = re.split(r"Indeed\s*[-–]\s*one search", body, maxsplit=1)[0]

    if not result.location:
        m = _LOCATION_KEYWORDS.search(body_no_footer) or _LOCATION_KEYWORDS.search(subject)
        if m:
            result.location = _clean(m.group(1))
    if not result.location:
        m = _LOCATION_CITY_STATE.search(body_no_footer) or _LOCATION_CITY_STATE.search(subject)
        if m:
            result.location = _clean(m.group(1))
    if not result.location:
        if _REMOTE_ANYWHERE.search(body) or _REMOTE_ANYWHERE.search(subject):
            result.location = "Remote"

    m = _SALARY.search(body) or _SALARY.search(subject)
    if m:
        result.salary_range = m.group(0).strip()

    return result
