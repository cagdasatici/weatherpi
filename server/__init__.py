"""Server package initializer - expose the Flask app for imports in tests.
"""
from .app import app

__all__ = ["app"]
