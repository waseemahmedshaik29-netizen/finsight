"""DATABASE_URL and dotenv resolution are shared with the application."""
from alembic import context

from app.db import Base, engine


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Use an online connection: the baseline validates existing tables.")

connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with engine.connect() as connection:
        run(connection)
