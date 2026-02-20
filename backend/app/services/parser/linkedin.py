"""Regex-based parser for LinkedIn application confirmation emails.

Sender: jobs-noreply@linkedin.com / jobs-listings@linkedin.com

Plain-text body format (most common — text/plain part):
  Application confirmation:
    "Your application was sent to COMPANY\r\n\r\nROLE\r\nCOMPANY\r\nLOCATION\r\n..."
  Rejection / update:
    "Your update from COMPANY\r\n\r\nROLE\r\nCOMPANY\r\nLOCATION\r\n..."

Subject formats:
  Confirmation: "Lakshmi, your application was sent to Open Systems Inc."
  Rejection:    "Your application to Software Engineer at Evolve Group"
"""
import re

from app.services.parser.base import ParseResult

MIDDLE_DOT = "\u00b7"   # LinkedIn uses U+00B7 in HTML emails (fallback)

# ── Subject patterns ──────────────────────────────────────────────────────────

# "Your application to Senior Engineer at Google"  (rejection email subjects)
_SUBJECT_ROLE_COMPANY = re.compile(
    r"Your application to (.+?) at (.+?)$",
    re.IGNORECASE,
)

# "Lakshmi, your application was sent to Open Systems Inc."
_SUBJECT_COMPANY_ONLY = re.compile(
    r"(?:application(?:\s+was)?\s+sent\s+to|applied\s+to)\s+(.+?)(?:\s*[\|\-]|$)",
    re.IGNORECASE,
)

# ── Body patterns (fallback for older / one-line formats) ─────────────────────

# Older format: "sent to [Company] for [Role]" in same sentence
_BODY_SENT_TO_FOR = re.compile(
    r"(?:[\w\s]+,\s+)?(?:your\s+)?application\s+was\s+sent\s+to\s+"
    r"(.{2,80}?)\s+for\s+(?:the\s+)?(.{1,120}?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)

# "You applied for [Role] at [Company]"
_BODY_ROLE_COMPANY = re.compile(
    r"(?:applied\s+for|application\s+for)\s+(.{1,100}?)\s+at\s+(.{1,100}?)(?:\n|\.|,|$)",
    re.IGNORECASE,
)

# Labelled: "Position: Software Engineer" or "Role: ..."
_BODY_POSITION_LABEL = re.compile(
    r"(?:Position|Role|Job\s+Title)[:\s]+([^\n,\.]{3,120})",
    re.IGNORECASE,
)

# Final fallback: "remote" anywhere in body
_REMOTE_ANYWHERE = re.compile(r"\bremote\b", re.IGNORECASE)


def _process_location(raw: str) -> "str | None":
    """
    Normalize a raw location string from LinkedIn.

    Examples:
      "United States (Remote)"  -> "Remote"
      "New York, United States" -> "New York"
      "Seattle, WA"             -> "Seattle, WA"
      "United States"           -> "United States"
      "Remote"                  -> "Remote"
    """
    if not raw:
        return None
    raw = raw.strip()

    if re.search(r"\bremote\b", raw, re.IGNORECASE):
        return "Remote"
    if re.search(r"\bhybrid\b", raw, re.IGNORECASE):
        return "Hybrid"

    # "City, ST" — US state abbreviation
    m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b", raw)
    if m:
        return "{}, {}".format(m.group(1), m.group(2))

    # "City, Country" — keep just the city e.g. "New York, United States" -> "New York"
    m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),", raw.strip())
    if m:
        return m.group(1).strip()

    if len(raw) <= 40:
        return raw

    return None


def _extract_via_company(company: str, body: str):
    """
    Given the known company name, extract role and location from the body.

    Handles two formats:

    1. Plain-text (multiline) — the common text/plain part:
         "sent to COMPANY\\r\\n\\r\\nROLE\\r\\nCOMPANY\\r\\nLOCATION"
       Strategy: find "sent to COMPANY" anchor → find COMPANY on its own line
       → role = last non-empty line before that → location = first line after.

    2. HTML-stripped (single-line with middle dot) — fallback:
         "sent to COMPANY. ROLE COMPANY · LOCATION"

    Returns (role, location) — either may be None.
    """
    c_esc = re.escape(company.rstrip(". "))
    role = None
    location = None

    # ── 1. Multiline plain-text format ──────────────────────────────────────
    sent_pat = re.compile(
        r"(?:sent\s+to\s+|update\s+from\s+)" + c_esc + r"\b",
        re.IGNORECASE,
    )
    sent_m = sent_pat.search(body)
    if sent_m:
        # Find COMPANY appearing alone on its own line after the anchor
        company_line_pat = re.compile(
            r"^[ \t]*" + c_esc + r"[.\s]*$",
            re.IGNORECASE | re.MULTILINE,
        )
        comp_m = company_line_pat.search(body, sent_m.end())
        if comp_m:
            # Role: last non-empty, non-header line before the company line
            before = body[:comp_m.start()]
            lines = [l.rstrip("\r") for l in before.split("\n")]
            for line in reversed(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                # Skip lines that are clearly headers / email boilerplate
                if re.search(
                    r"application was sent to|update from|dear\b|^hi\b|^hello\b|"
                    r"^your\b|͏|\[",
                    stripped, re.IGNORECASE,
                ):
                    continue
                role = stripped
                break

            # Location: first non-empty, non-junk line after the company line
            after = body[comp_m.end():]
            for loc_line in after.split("\n"):
                stripped = loc_line.rstrip("\r").strip()
                if not stripped:
                    continue
                if re.search(
                    r"http|view job|learn why|email was intended|unsubscribe|"
                    r"^\[|^Never miss",
                    stripped, re.IGNORECASE,
                ):
                    continue
                location = _process_location(stripped)
                break

    # ── 2. HTML-stripped inline format with U+00B7 middle dot ───────────────
    if not location:
        loc_pat = re.compile(
            c_esc + r"[. ]*\s*" + re.escape(MIDDLE_DOT) +
            r"\s*([^\n" + re.escape(MIDDLE_DOT) + r"]{3,120}?)"
            r"(?=\s{2,}|\s*Applied|\s*$|\s*Never|\s*Please)",
            re.IGNORECASE,
        )
        lm = loc_pat.search(body)
        if lm:
            location = _process_location(lm.group(1).strip())

    if not role:
        role_pat = re.compile(
            r"(?:sent\s+to\s+|update\s+from\s+)" + c_esc +
            r"[.\s]+" +
            r"([A-Z][^" + re.escape(MIDDLE_DOT) + r"\n]{2,120}?)" +
            r"\s+" + c_esc +
            r"[. ]*\s*" + re.escape(MIDDLE_DOT),
            re.IGNORECASE,
        )
        rm = role_pat.search(body)
        if rm:
            role = rm.group(1).strip()

    return role, location


def parse(subject: str, body: str) -> ParseResult:
    result = ParseResult(platform="linkedin")

    # Skip LinkedIn notification emails that aren't application confirmations
    if re.search(
        r"application was viewed by|viewed your (?:linkedin\s+)?profile|"
        r"recruiter (?:at|from) .+ viewed",
        subject, re.IGNORECASE,
    ):
        result.confidence = 0.0
        return result

    # ── 1. Subject extraction ─────────────────────────────────────────────────

    m = _SUBJECT_ROLE_COMPANY.search(subject)
    if m:
        result.job_title = m.group(1).strip()
        result.company_name = m.group(2).strip()
    else:
        m = _SUBJECT_COMPANY_ONLY.search(subject)
        if m:
            result.company_name = m.group(1).strip()

    # ── 2. Body: fill missing company / role ──────────────────────────────────

    if not result.job_title or not result.company_name:
        m = _BODY_SENT_TO_FOR.search(body)
        if m:
            if not result.company_name:
                result.company_name = m.group(1).strip()
            if not result.job_title:
                result.job_title = m.group(2).strip()

    if not result.job_title or not result.company_name:
        m = _BODY_ROLE_COMPANY.search(body)
        if m:
            if not result.job_title:
                result.job_title = m.group(1).strip()
            if not result.company_name:
                result.company_name = m.group(2).strip()

    # ── 3. Use company as anchor to extract role + location from body ─────────
    #
    # LinkedIn plain-text body:
    #   "... sent to COMPANY\r\n\r\nROLE\r\nCOMPANY\r\nLOCATION\r\n..."
    #
    # We already know the company — use it to find the role and location.

    if result.company_name:
        role, location = _extract_via_company(result.company_name, body)
        if not result.job_title and role:
            result.job_title = role
        if not result.location and location:
            result.location = location

    # ── 4. Labelled position field (rare) ─────────────────────────────────────

    if not result.job_title:
        m = _BODY_POSITION_LABEL.search(body)
        if m:
            result.job_title = m.group(1).strip()

    # ── 5. Location fallback: "remote" anywhere ───────────────────────────────

    if not result.location:
        if _REMOTE_ANYWHERE.search(body) or _REMOTE_ANYWHERE.search(subject):
            result.location = "Remote"

    return result
