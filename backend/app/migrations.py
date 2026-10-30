"""Run the same migration chain from the CLI or local application startup."""
from pathlib import Path

from alembic import command
from alembic.config import Config


def configuration(connection=None):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade_database(engine):
    with engine.begin() as connection:
        command.upgrade(configuration(connection), "head")
