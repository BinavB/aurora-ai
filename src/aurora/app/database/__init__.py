"""Database layer: the SQLite persistence engine.

Provides an async, serialized connection and the schema. Higher layers use
repositories (in ``memory``) rather than touching SQL directly.
"""

from aurora.app.database.engine import Database
from aurora.app.database.schema import SCHEMA
from aurora.app.database.turso import TursoDatabase

__all__ = ["Database", "SCHEMA", "TursoDatabase", "build_database"]


def build_database(sqlite_path: str, turso_url: str = "", turso_token: str = ""):
    if turso_url:
        return TursoDatabase(turso_url, turso_token)
    return Database(sqlite_path)
