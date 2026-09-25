from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..tasks.errors import Conflict


class Database:
    def __init__(self, path: str):
        self.engine = create_engine(
            URL.create("sqlite+pysqlite", database=path),
            connect_args={"timeout": 5, "check_same_thread": False},
        )
        event.listen(self.engine, "connect", self.configure_sqlite)
        event.listen(self.engine, "begin", self.begin_transaction)
        self.migrate()

    @staticmethod
    def configure_sqlite(connection, _record):
        # Driver-level connection settings, not application queries.
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @staticmethod
    def begin_transaction(connection):
        # SQLite ignores SELECT FOR UPDATE. Reserve the writer before reading
        # revisions or leases so the entire check-and-mutate operation is atomic.
        mode = (
            "BEGIN IMMEDIATE"
            if connection.get_execution_options().get("write")
            else "BEGIN"
        )
        connection.exec_driver_sql(mode)

    def migrate(self):
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).parent / "migrations")
        )
        with (
            self.engine.connect().execution_options(write=True) as connection,
            connection.begin(),
        ):
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    @contextmanager
    def session(self, write=False):
        try:
            with (
                self.engine.connect().execution_options(write=write) as connection,
                Session(connection, expire_on_commit=False) as session,
                session.begin(),
            ):
                yield session
        except OperationalError as exc:
            if "locked" in str(exc.orig):
                raise Conflict(
                    "database_busy", "Database busy; retry shortly", 503
                ) from exc
            raise
