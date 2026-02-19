"""LLM fallback parser using Claude claude-haiku-4-5 with structured tool_use output."""
import json

import anthropic

from app.config import settings
from app.services.parser.base import ParseResult

_EXTRACTION_TOOL = {
    "name": "extract_job_details",
    "description": "Extract job application details from an email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "The name of the company the user applied to. Null if not found.",
            },
            "job_title": {
                "type": "string",
                "description": "The job title or position the user applied for. Null if not found.",
            },
            "location": {
                "type": "string",
                "description": "Job location (e.g. 'Remote', 'New York, NY', 'Hybrid'). Null if not found.",
            },
            "salary_range": {
                "type": "string",
                "description": "Salary or compensation range if mentioned (e.g. '$120k-$150k'). Null if not mentioned.",
            },
        },
        "required": ["company_name", "job_title", "location", "salary_range"],
    },
}

_SYSTEM_PROMPT = (
    "You are an information extraction assistant. "
    "Extract job application details from the provided email. "
    "Return null for any field that is not clearly present in the email. "
    "Do not guess or invent information."
)


def parse(sender: str, subject: str, body: str) -> ParseResult:
    """Use Claude claude-haiku-4-5 to extract job details when regex confidence is low."""
    if not settings.anthropic_api_key:
        return ParseResult(platform="direct")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    email_text = f"From: {sender}\nSubject: {subject}\n\n{body[:3000]}"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            tools=[_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_job_details"},
            messages=[{"role": "user", "content": email_text}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_job_details":
                data = block.input
                return ParseResult(
                    company_name=data.get("company_name") or None,
                    job_title=data.get("job_title") or None,
                    location=data.get("location") or None,
                    salary_range=data.get("salary_range") or None,
                    platform="direct",
                )
    except Exception:
        pass

    return ParseResult(platform="direct")
