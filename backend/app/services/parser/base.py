"""Base types and routing logic for the hybrid parsing engine."""
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class ParseResult:
    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None
    salary_range: str | None = None
    platform: str = "direct"
    confidence: float = 0.0

    def compute_confidence(self) -> "ParseResult":
        """
        Recalculate confidence: each extracted field adds 0.25.
        Full 4/4 fields = 1.0 confidence.
        """
        score = sum(
            0.25
            for val in [self.company_name, self.job_title, self.location, self.salary_range]
            if val
        )
        self.confidence = score
        return self


def parse_email(sender: str, subject: str, body: str) -> ParseResult:
    """
    Route to the appropriate regex parser based on sender domain,
    then fall back to the LLM parser if confidence is below the threshold.
    """
    from app.services.parser import linkedin, indeed, generic, llm

    sender_lower = sender.lower()

    if "linkedin.com" in sender_lower:
        result = linkedin.parse(subject, body)
    elif "indeed.com" in sender_lower:
        result = indeed.parse(subject, body)
    else:
        result = generic.parse(sender, subject, body)

    result.compute_confidence()

    if result.confidence < settings.llm_confidence_threshold:
        llm_result = llm.parse(sender, subject, body)
        llm_result.compute_confidence()
        # Use the LLM result's platform-neutral extraction, but keep the
        # regex parser's platform detection (linkedin / indeed / direct).
        llm_result.platform = result.platform
        # Only upgrade to the LLM result if it extracted more info than
        # the regex parser did — avoids losing good regex data when the
        # LLM API key is invalid or the LLM returns nothing useful.
        if llm_result.confidence > result.confidence:
            return llm_result

    return result
