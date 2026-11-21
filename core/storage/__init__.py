"""
Storage backends for the grid data.

``GridStore`` (in ``core.storage.base``) is the interface; implementations
follow in later commits (SQLite first). See TODO.md 2.6.
"""

from core.storage.base import Dataset, GridStore, Row

__all__ = ["Dataset", "GridStore", "Row"]
