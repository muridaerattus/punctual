from alembic import context
from sqlalchemy import URL, create_engine

from punctual.config import Settings
from punctual.db.models import Base

config = context.config
target_metadata = Base.metadata
database_url = URL.create("sqlite+pysqlite", database=Settings().db)


def run(connection):
    context.configure(
        connection=connection, target_metadata=target_metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif connection := config.attributes.get("connection"):
    run(connection)
else:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        run(connection)
