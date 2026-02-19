import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 'linkedin' | 'indeed' | 'direct'
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="direct")

    # 'applied' | 'phone_screen' | 'technical' | 'offer' | 'rejected' | 'ghosted'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="applied")

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Gmail message ID used for deduplication
    email_message_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # Confidence score from parser (0–1). Values < 0.7 indicate LLM was used.
    parse_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    manually_overridden: Mapped[bool] = mapped_column(Boolean, default=False)

    raw_email_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="applications")
