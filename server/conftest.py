"""Test fixtures for the nb.wtf server.

`app.py` reads its config (WIKI_BASE_URL, SQLITE_PATH) from the environment
at import time, so we set those here *before* importing the app, and point
the DB at a throwaway temp file per test session. No network is touched:
redirect tests seed the links table directly, and the scrape parser is
exercised against fixture HTML.
"""

import importlib
import os

import pytest

# Canonical wiki base used across the tabular tests. Trailing slash matters:
# app.py builds wiki links with urljoin(WIKI_BASE_URL, slug).
WIKI_BASE_URL = "https://www.noisebridge.net/wiki/"


@pytest.fixture(scope="session")
def app_module(tmp_path_factory):
    """Import app.py once, wired to a temp sqlite DB and the test wiki base."""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["WIKI_BASE_URL"] = WIKI_BASE_URL
    os.environ["SQLITE_PATH"] = str(db_path)

    import app

    importlib.reload(app)
    return app


@pytest.fixture
def seed(app_module):
    """Replace the links table with the given {slug: url} mapping."""

    def _seed(mapping):
        app_module.update_db(mapping)

    return _seed


@pytest.fixture
def client(app_module):
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()
