"""Regex-based parser for LinkedIn application confirmation emails.

Sender domain: jobs-listings@linkedin.com / jobalerts@linkedin.com
Subject patterns: "Your application was sent to <Company>"
"""
import re

from app.services.parser.base import ParseResult

# LinkedIn subjects: "Your application was sent to Stripe"
_SUBJECT_COMPANY = re.compile(
    r"(?:application(?:\s+was)?\s+sent\s+to|applied\s+to)\s+(.+?)(?:\s*[\|\-]|$)",
    re.IGNORECASE,
)

# Body: "You applied for Senior Product Designer at Google"
_BODY_ROLE_COMPANY = re.compile(
    r"(?:applied\s+for|application\s+for)\s+(.+?)\s+at\s+(.+?)(?:\n|\.|\,|$)",
    re.IGNORECASE,
)

# Location patterns
_LOCATION = re.compile(
    r"\b(Remote|Hybrid|On-?site|[A-Z][a-z]+(?:,\s*[A-Z]{2})?)\b",
    re.MULTILINE,
)

# Salary: "$120,000 - $150,000" or "120k - 150k"
_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)


def parse(subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="linkedin")

    # Extract company from subject
    m = _SUBJECT_COMPANY.search(subject)
    if m:
        result.company_name = m.group(1).strip()

    # Extract role and possibly company from body
    m = _BODY_ROLE_COMPANY.search(body)
    if m:
        result.job_title = m.group(1).strip()
        if not result.company_name:
            result.company_name = m.group(2).strip()

    # Location
    m = _LOCATION.search(body)
    if m:
        result.location = m.group(1).strip()

    # Salary
    m = _SALARY.search(body)
    if m:
        result.salary_range = m.group(0).strip()

    return result
