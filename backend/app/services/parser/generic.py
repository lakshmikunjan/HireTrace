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

# "Thank you for applying to [Role] at [Company]"
_ROLE_COMPANY_1 = re.compile(
    r"(?:applying\s+(?:for|to)\s+(?:the\s+)?(?:position\s+of\s+)?|applied\s+for\s+)"
    r"(.+?)\s+at\s+(.+?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "Application for: Senior Designer | Company Name"
_ROLE_COMPANY_2 = re.compile(
    r"(?:Application\s+for[:\s]+|Position[:\s]+)(.+?)(?:\s*\|\s*|\s+at\s+)(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# Standalone company name lines (e.g. "Company: Google" or "Hiring Company: Google")
_COMPANY_LABEL = re.compile(
    r"(?:Company|Employer|Organization|Hiring\s+Company)[:\s]+([A-Z][A-Za-z0-9&\s,\.]{1,60})",
    re.IGNORECASE,
)

_JOB_TITLE_LABEL = re.compile(
    r"(?:Job\s+Title|Position|Role)[:\s]+(.+?)(?:\n|$)",
    re.IGNORECASE,
)

_LOCATION = re.compile(
    r"(?:Location[:\s]+)?(?:\b)(Remote|Hybrid|On-?site|[A-Z][a-z]+(?:,\s*[A-Z]{2})?)(?:\b)",
    re.MULTILINE,
)

_SALARY = re.compile(
    r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hr|hour))?|\d+[kK]\s*[-–]\s*\d+[kK]",
)


def parse(sender: str, subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="direct")

    # Try pattern 1: "applying for [role] at [company]"
    m = _ROLE_COMPANY_1.search(body) or _ROLE_COMPANY_1.search(subject)
    if m:
        result.job_title = m.group(1).strip()
        result.company_name = m.group(2).strip()

    # Try pattern 2: "Application for: Role | Company"
    if not result.job_title:
        m = _ROLE_COMPANY_2.search(body) or _ROLE_COMPANY_2.search(subject)
        if m:
            result.job_title = m.group(1).strip()
            result.company_name = m.group(2).strip()

    # Try labelled fields
    if not result.job_title:
        m = _JOB_TITLE_LABEL.search(body)
        if m:
            result.job_title = m.group(1).strip()

    if not result.company_name:
        m = _COMPANY_LABEL.search(body)
        if m:
            result.company_name = m.group(1).strip()

    # Location
    m = _LOCATION.search(body)
    if m:
        result.location = m.group(1).strip()

    # Salary
    m = _SALARY.search(body)
    if m:
        result.salary_range = m.group(0).strip()

    return result
