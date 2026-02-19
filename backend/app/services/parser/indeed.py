"""Regex-based parser for Indeed application confirmation emails.

Sender domain: confirmations@indeed.com / no-reply@indeed.com
Subject patterns: "Your application to <Company> was sent"
"""
import re

from app.services.parser.base import ParseResult

# Subject: "Your application to Google was sent"
_SUBJECT_COMPANY = re.compile(
    r"application\s+to\s+(.+?)\s+(?:was\s+sent|has\s+been|received)",
    re.IGNORECASE,
)

# Body: "You applied for the position of Senior Engineer"
_BODY_ROLE = re.compile(
    r"(?:applied\s+for\s+the\s+(?:position\s+of\s+)?|position:\s*)(.+?)(?:\n|at\s|\.|$)",
    re.IGNORECASE,
)

# Body: "at Google" or "Company: Google"
_BODY_COMPANY = re.compile(
    r"(?:Company:\s*|at\s+)([A-Z][A-Za-z0-9&\s,\.]+?)(?:\n|$|\.|,)",
    re.MULTILINE,
)

_LOCATION = re.compile(
    r"\b(Remote|Hybrid|On-?site|[A-Z][a-z]+(?:,\s*[A-Z]{2})?)\b",
    re.MULTILINE,
)

_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)


def parse(subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="indeed")

    m = _SUBJECT_COMPANY.search(subject)
    if m:
        result.company_name = m.group(1).strip()

    m = _BODY_ROLE.search(body)
    if m:
        result.job_title = m.group(1).strip()

    if not result.company_name:
        m = _BODY_COMPANY.search(body)
        if m:
            result.company_name = m.group(1).strip()

    m = _LOCATION.search(body)
    if m:
        result.location = m.group(1).strip()

    m = _SALARY.search(body)
    if m:
        result.salary_range = m.group(0).strip()

    return result
