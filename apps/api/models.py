from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SystemMetadata(Base):
    __tablename__: str = "system_metadata"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class InstrumentRecord(Base):
    __tablename__: str = "instruments"

    instrument_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(100))
    asset_class: Mapped[str] = mapped_column(String(30), default="equity")
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ProviderSymbolMapping(Base):
    __tablename__: str = "provider_symbol_mappings"
    __table_args__: tuple[CheckConstraint, Index] = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_mapping_window"),
        Index("ix_provider_symbol_active", "provider", "provider_symbol", "valid_to"),
    )

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider_symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"), index=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
