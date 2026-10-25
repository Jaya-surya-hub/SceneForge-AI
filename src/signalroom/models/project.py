"""SQLAlchemy model for research projects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from signalroom.db.base import Base

if TYPE_CHECKING:
    from signalroom.models.run import Run
    from signalroom.models.question import Question


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_domains: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["incubrix.com"])
    default_markets: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["US", "UK", "IN"])
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    runs: Mapped[List[Run]] = relationship("Run", back_populates="project", cascade="all, delete-orphan")
    questions: Mapped[List[Question]] = relationship("Question", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project id={self.id} slug={self.slug} name='{self.name}'>"
