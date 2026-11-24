"""Shared fixtures. The app under test is chosen with NOTESVC_APP_DIR."""
import os
import sys

import pytest

APP_DIR = os.environ.get("NOTESVC_APP_DIR")
if not APP_DIR:
    raise RuntimeError("set NOTESVC_APP_DIR to the app directory (the one containing notesvc/)")
sys.path.insert(0, os.path.abspath(APP_DIR))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import Env  # noqa: E402


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)
