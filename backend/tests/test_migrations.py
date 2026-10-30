"""Upgrade fresh and pre-Alembic databases; never use a personal database here."""
import os
from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db import Base, Cache, Portfolio, Position, Snapshot
from app.migrations import configuration, upgrade_database

URLS = [None]
if os.getenv("MIGRATION_TEST_DATABASE_URL"):
    URLS.append(os.environ["MIGRATION_TEST_DATABASE_URL"])


@pytest.fixture(params=URLS, ids=lambda url: "postgresql" if url else "sqlite")
def database(request, tmp_path):
    # The optional URL MUST point to an empty disposable CI database.
    engine = create_engine(request.param or f"sqlite:///{tmp_path / 'migration.db'}")
    assert not inspect(engine).get_table_names(), "Use an empty migration test database"
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()


def assert_head_and_schema(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_initial"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_fresh_upgrade_repeat_and_downgrade(database):
    upgrade_database(database)
    assert_head_and_schema(database)
    upgrade_database(database)
    assert_head_and_schema(database)
    with database.begin() as connection:
        command.check(configuration(connection))
        command.downgrade(configuration(connection), "base")
    assert not (set(Base.metadata.tables) & set(inspect(database).get_table_names()))
    upgrade_database(database)
    assert_head_and_schema(database)


def test_adopt_current_schema_preserves_all_rows_and_constraints(database):
    Base.metadata.create_all(database)  # Exact pre-Alembic startup behavior.
    timestamp = datetime(2026, 10, 5, tzinfo=timezone.utc)
    with database.begin() as connection:
        connection.execute(Portfolio.__table__.insert().values(id=7, name="Legacy", benchmark="SPY", cash=1234.5))
        connection.execute(Position.__table__.insert().values(id=8, portfolio_id=7, ticker="MSFT", quantity=2.5, cost_basis=300))
        connection.execute(Snapshot.__table__.insert().values(id=9, portfolio_id=7, created_at=timestamp, payload={"value": 2345.67, "holdings": ["MSFT"]}))
        connection.execute(Cache.__table__.insert().values(key="legacy", updated=timestamp, payload={"prices": [1, 2, 3]}))
        before = {table.name: connection.execute(select(table)).all() for table in Base.metadata.sorted_tables}
    upgrade_database(database)
    upgrade_database(database)
    assert_head_and_schema(database)
    with database.connect() as connection:
        after = {table.name: connection.execute(select(table)).all() for table in Base.metadata.sorted_tables}
        assert before == after
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(Position.__table__.insert().values(portfolio_id=7, ticker="MSFT", quantity=1, cost_basis=1))


@pytest.mark.parametrize("drift", ["partial", "column", "unique", "foreign_key", "primary_key"])
def test_incompatible_legacy_schema_is_not_adopted(database, drift):
    metadata = Base.metadata
    if drift == "partial":
        Portfolio.__table__.create(database)
    else:
        # Modify copies so the application's metadata is never mutated.
        from sqlalchemy import MetaData, UniqueConstraint, ForeignKeyConstraint
        copied = MetaData()
        for table in metadata.sorted_tables:
            table.to_metadata(copied)
        if drift == "unique":
            table = copied.tables["positions"]
            table.constraints.remove(next(c for c in table.constraints if isinstance(c, UniqueConstraint)))
        elif drift == "foreign_key":
            table = copied.tables["positions"]
            constraint = next(c for c in table.constraints if isinstance(c, ForeignKeyConstraint))
            constraint.ondelete = None
        elif drift == "primary_key":
            table = copied.tables["cache"]
            table.primary_key._columns.remove(table.c.key)
            table.c.key.primary_key = False
        copied.create_all(database)
        if drift == "column":
            with database.begin() as connection:
                connection.execute(text("ALTER TABLE portfolios ADD COLUMN unexpected INTEGER"))
    with pytest.raises(RuntimeError, match="does not match baseline"):
        upgrade_database(database)
    with database.connect() as connection:
        if "alembic_version" in inspect(database).get_table_names():
            assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 0
