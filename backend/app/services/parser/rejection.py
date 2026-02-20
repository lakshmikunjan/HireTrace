"""Extract company name from rejection/assessment emails for status matching."""
import re

# Subject: "An update on your application from New Legacy Charter School"
# Subject: "Your application to Senior Engineer at Google — update"
_SUBJECT_FROM_COMPANY = re.compile(
    r"(?:application|update)\s+from\s+(.{2,80}?)(?:\s*[\|\-\n]|$)",
    re.IGNORECASE,
)

_SUBJECT_AT_COMPANY = re.compile(
    r"(?:application|update).{0,40}?\bat\s+([A-Z][A-Za-z0-9&\s\.\-]{1,60}?)(?:\s*[,\.\|\-]|$)",
    re.IGNORECASE,
)

# Subject: "Regarding your Application to FanDuel" / "Update on your application to Stripe"
_SUBJECT_TO_COMPANY = re.compile(
    r"(?:application|update).{0,30}?\bto\s+([A-Z][A-Za-z0-9&\s\.\-]{2,60}?)(?:\s*[,\.\|\-\n]|$)",
    re.IGNORECASE,
)

# Body: "your application to/at/with [Company]"
_BODY_APPLICATION = re.compile(
    r"application\s+(?:to|at|with)\s+([A-Z][A-Za-z0-9&\s\.\-]{2,60}?)(?:\s*[,\.\n]|$)",
    re.IGNORECASE,
)

# Body: "Company: Google" label
_BODY_COMPANY_LABEL = re.compile(
    r"(?:Company|Employer)[:\s]+([A-Z][A-Za-z0-9&\s\.\-]{2,60}?)(?:\s*[,\.\n]|$)",
    re.IGNORECASE,
)

# Generic words / ATS platform names that are NOT real company names.
_NOISE = {
    # Job board / platform names
    "indeed", "linkedin", "glassdoor", "ziprecruiter", "monster", "dice",
    "careerbuilder", "simplyhired", "indeedemail", "indeedapply",
    # ATS systems (send emails ON BEHALF of companies, not AS the company)
    "workday", "myworkday", "greenhouse", "lever", "ashby", "icims",
    "taleo", "smartrecruiters", "brassring", "successfactors", "njoyn",
    "jobvite", "applytojob", "jobscore", "bamboohr", "recruiterbox",
    "schoolinks", "ultipro", "paycom", "paylocity", "dayforce", "ceridian",
    "cybercoders", "kforce", "staffing",
    # Generic mail/tech words
    "mailer", "noreply", "donotreply", "notification", "notifications",
    "news", "newsletter", "msg", "mail", "email", "support", "app",
    "hr", "jobs", "recruiting", "recruitment", "careers", "talent", "hiring",
    # Generic English words that slip through
    "candidates", "applicants", "team", "company", "employer", "future",
    "us", "our", "we", "time", "this", "the",
}

# Words that indicate the match is a sentence fragment, not a company name
_LEADING_STOPWORDS = {
    "in", "at", "on", "by", "for", "of", "to", "a", "an", "the",
    "this", "that", "these", "those", "we", "our", "your", "my",
}

# Patterns that indicate garbage was captured (dates, phrases)
_GARBAGE_PATTERN = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b"
    r"|\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"
    r"|we have decided|we are unable|moving forward|in the future|at this time",
    re.IGNORECASE,
)


def _clean(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip().rstrip(".,;:")
    # Length guard: must be at least 4 chars, at most 80
    if len(name) < 4 or len(name) > 80:
        return None
    # Reject if the extracted text is clearly a sentence fragment (starts with stopword)
    first_word = name.split()[0].lower()
    if first_word in _LEADING_STOPWORDS or first_word in _NOISE:
        return None
    # Reject if it looks like a date or common rejection phrase
    if _GARBAGE_PATTERN.search(name):
        return None
    # All lowercase → not a proper noun / company name
    if name == name.lower():
        return None
    # Check noise list (whole name, and without spaces)
    if name.lower() in _NOISE or name.lower().replace(" ", "") in _NOISE:
        return None
    # Check if the domain portion (for hyphenated names like "greenhouse-mail") is noise
    for part in re.split(r"[-_]", name.lower()):
        if part in _NOISE:
            return None
    return name


def extract_company(sender: str, subject: str, body: str) -> str | None:
    """Best-effort extraction of company name from a rejection/assessment email."""

    # 1. Subject is most reliable — check it first
    for pattern in (_SUBJECT_FROM_COMPANY, _SUBJECT_AT_COMPANY, _SUBJECT_TO_COMPANY):
        m = pattern.search(subject)
        if m:
            c = _clean(m.group(1))
            if c:
                return c

    # 2. Body: labelled fields are precise
    m = _BODY_COMPANY_LABEL.search(body)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    # 3. Body: "your application to/at [Company]" in first 800 chars
    m = _BODY_APPLICATION.search(body[:800])
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    # 4. Last resort: sender domain (no-reply@stripe.com → "Stripe")
    #    Only use if the domain looks like a real company (not an ATS/platform)
    domain_match = re.search(r"@(?:[\w\-]+\.)*?([\w\-]+)\.\w+$", sender)
    if domain_match:
        domain = domain_match.group(1)
        # Skip generic mail infrastructure and known ATS domains
        if domain.lower() not in _NOISE and domain.lower() not in {
            "gmail", "yahoo", "outlook", "hotmail", "live", "icloud",
            "noreply", "no-reply", "sendgrid", "mailgun", "amazonses",
            "sparkpost", "mandrillapp",
        }:
            # Prefer title-case for multi-char domains
            company = domain.upper() if len(domain) <= 4 else domain.capitalize()
            c = _clean(company)
            if c:
                return c

    return None
