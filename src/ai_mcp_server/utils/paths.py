from __future__ import annotations

from pathlib import Path

from .path_util import (
    data_dir,
    probe_assets_dir,
)
from .path_util import (
    db_path as _db_path,
)


def config_dir() -> Path:
    return data_dir()


def db_path() -> Path:
    return _db_path()


def assets_dir() -> Path:
    return probe_assets_dir()
