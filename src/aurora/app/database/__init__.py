"""Database layer: the SQLite persistence engine.

Provides an async, serialized connection and the schema. Higher layers use
repositories (in ``memory``) rather than touching SQL directly.
"""

from aurora.app.database.engine import Database
from aurora.app.database.schema import SCHEMA

__all__ = ["Database", "SCHEMA"]
