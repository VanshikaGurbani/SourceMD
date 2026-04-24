"""SQLAlchemy ORM models for SourceMD."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class Verdict(str, enum.Enum):
    """Possible classifications for a single extracted claim."""

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class User(Base):
    """Registered user with email/password auth."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    evaluations: Mapped[list["Evaluation"]] = relationship(
        "Evaluation", back_populates="user", cascade="all, delete-orphan"
    )


class Evaluation(Base):
    """One end-to-end run of the trust pipeline for a (question, answer) pair."""

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    ai_answer: Mapped[str] = mapped_column(Text, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ragas_faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    ragas_context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    follow_up_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    user: Mapped[User | None] = relationship("User", back_populates="evaluations")
    claims: Mapped[list["Claim"]] = relationship(
        "Claim",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="Claim.id",
    )


class Claim(Base):
    """A single atomic claim extracted from the AI answer with its scoring."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[Verdict] = mapped_column(
        Enum(Verdict, name="verdict_enum"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    evaluation: Mapped[Evaluation] = relationship("Evaluation", back_populates="claims")
