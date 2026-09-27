"""Filesystem paths that work both from the source tree and the API image."""

from pathlib import Path


def _find_project_root(start: Path) -> Path:
    """Find the directory containing the runtime model and artifact folders.

    Locally the API lives under ``apps/api/app``; the Docker image copies that
    package to ``/app/app``.  A fixed ``parents[n]`` index therefore cannot
    represent both layouts.
    """
    for candidate in (start, *start.parents):
        if (candidate / "models").is_dir() and (candidate / "artifacts").is_dir():
            return candidate
    raise RuntimeError(f"Could not locate project root from {start}")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
