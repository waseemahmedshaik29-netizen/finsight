"""Baseline the original four-table schema without rewriting existing data.

This definition is deliberately frozen; never import current application models here.
"""
from alembic import op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def baseline_metadata():
    metadata = sa.MetaData()
    sa.Table(
        "portfolios", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("benchmark", sa.String(12), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
    )
    sa.Table(
        "positions", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(12), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("cost_basis", sa.Float(), nullable=False),
        sa.UniqueConstraint("portfolio_id", "ticker"),
    )
    sa.Table(
        "snapshots", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    sa.Table(
        "cache", metadata,
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
    )
    return metadata


def upgrade():
    connection = op.get_bind()
    metadata = baseline_metadata()
    existing = set(sa.inspect(connection).get_table_names()) & set(metadata.tables)
    if existing:
        # Fail closed for partial or drifted legacy schemas; do not blindly stamp.
        context = MigrationContext.configure(connection, opts={
            "compare_type": True,
            "compare_server_default": True,
            "include_object": lambda obj, name, kind, reflected, other: (
                kind != "table" or name in metadata.tables
            ),
        })
        differences = compare_metadata(context, metadata)
        # Autogenerate does not check primary keys; verify them explicitly.
        inspector = sa.inspect(connection)
        keys_match = all(
            inspector.get_pk_constraint(name)["constrained_columns"]
            == [column.name for column in metadata.tables[name].primary_key]
            for name in existing
        )
        if existing != set(metadata.tables) or differences or not keys_match:
            raise RuntimeError(
                "Existing FinSight schema does not match baseline 0001_initial. "
                "Back up the database and reconcile schema drift before upgrading; "
                "do not stamp an incompatible database."
            )
        return
    metadata.create_all(connection, checkfirst=False)


def downgrade():
    # Explicit downgrade to base is destructive, including adopted legacy rows.
    for name in ("snapshots", "positions", "cache", "portfolios"):
        op.drop_table(name)
