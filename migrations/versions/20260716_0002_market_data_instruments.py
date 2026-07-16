from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    _ = op.create_table(
        "instruments",
        sa.Column("instrument_id", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("asset_class", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("instrument_id"),
    )
    op.create_index("ix_instruments_exchange", "instruments", ["exchange"])
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
    _ = op.create_table(
        "provider_symbol_mappings",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_symbol", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_id", sa.String(length=100), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_mapping_window"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.instrument_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("provider", "provider_symbol", "valid_from"),
    )
    op.create_index(
        "ix_provider_symbol_active",
        "provider_symbol_mappings",
        ["provider", "provider_symbol", "valid_to"],
    )
    op.create_index(
        "ix_provider_symbol_mappings_instrument_id",
        "provider_symbol_mappings",
        ["instrument_id"],
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE provider_symbol_mappings
            ADD CONSTRAINT ex_provider_symbol_window
            EXCLUDE USING gist (
                provider WITH =,
                provider_symbol WITH =,
                tstzrange(valid_from, valid_to, '[)') WITH &&
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE provider_symbol_mappings
            ADD CONSTRAINT ex_provider_instrument_window
            EXCLUDE USING gist (
                provider WITH =,
                instrument_id WITH =,
                tstzrange(valid_from, valid_to, '[)') WITH &&
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_symbol_mappings_instrument_id",
        table_name="provider_symbol_mappings",
    )
    op.drop_index("ix_provider_symbol_active", table_name="provider_symbol_mappings")
    op.drop_table("provider_symbol_mappings")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_index("ix_instruments_exchange", table_name="instruments")
    op.drop_table("instruments")
