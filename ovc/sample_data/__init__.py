"""Tiny sample dataset bundled with OVC (see examples/sample/make_sample.py)."""

from importlib import resources
from pathlib import Path


def sample_path() -> Path:
    """Path of the bundled sample GeoPackage."""
    return Path(str(resources.files(__name__) / "ovc_sample.gpkg"))
