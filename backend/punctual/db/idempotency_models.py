from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IdempotencyReceipt(Base):
    """Immutable receipts, retained after task deletion; never store credentials."""

    __tablename__ = "idempotency_receipts"

    request_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    operation: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float)
