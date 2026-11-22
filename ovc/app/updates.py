"""Tell users about new OVC releases and install them.

At start-up the app asks GitHub for the latest published release of
AmmarYasser455/ovc. When it is newer than the running version the app shows
an update bar. How the update is applied depends on how OVC was installed:

* ``installer``: OVC was installed with ``OVC-Setup.exe``. The new installer
  is downloaded, its SHA-256 is checked against the ``OVC-Setup.exe.sha256``
  file published with the release, and it upgrades OVC in place and
  reopens it.
* ``portable``: OVC runs from the zip. The installer is offered as a
  download; installing once makes later updates one click.
* ``python``: OVC was installed with pip. The release page is offered.

The check sends one HTTPS request to api.github.com with the user agent
``OVC/<version>``; nothing about the user or their data is sent. Turn it off
in About, or with the ``OVC_NO_UPDATE_CHECK`` environment variable.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ovc import __version__

REPO = "AmmarYasser455/ovc"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALLER_NAME = "OVC-Setup.exe"
CHECKSUM_NAME = INSTALLER_NAME + ".sha256"
# Always the newest installer: the link a website can use.
DOWNLOAD_URL = f"https://github.com/{REPO}/releases/latest/download/{INSTALLER_NAME}"
TRUSTED_HOSTS = {
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
TIMEOUT = 8


class UpdateError(Exception):
    """An update could not be checked, downloaded or verified."""


def checks_enabled() -> bool:
    from ovc.app import settings

    if os.environ.get("OVC_NO_UPDATE_CHECK"):
        return False
    return bool(settings.load().get("check_for_updates", True))


def set_checks_enabled(enabled: bool) -> None:
    from ovc.app import settings

    settings.update({"check_for_updates": bool(enabled)})


def parse_version(text) -> tuple | None:
    """``"v3.6.0"`` -> ``(3, 6, 0)``; None for anything else."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(text or "").strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def install_kind() -> str:
    """``installer``, ``portable`` or ``python`` (see the module docstring)."""
    if not getattr(sys, "frozen", False):
        return "python"
    if (
        sys.platform == "win32"
        and (Path(sys.executable).parent / "unins000.exe").exists()
    ):
        return "installer"
    return "portable"


def _feed_url() -> str:
    return os.environ.get("OVC_UPDATE_FEED") or LATEST_API


def _check_url(url: str) -> str:
    """Only fetch from GitHub over HTTPS (any URL when a test feed is set)."""
    parsed = urlparse(url)
    if os.environ.get("OVC_UPDATE_FEED") and parsed.scheme in ("http", "https"):
        return url
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_HOSTS:
        raise UpdateError(f"Refusing to download from {url}")
    return url


def _open(url: str, accept: str = "*/*"):
    request = urllib.request.Request(
        _check_url(url),
        headers={"User-Agent": f"OVC/{__version__} (update check)", "Accept": accept},
    )
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def fetch_latest() -> dict:
    """The newest published release, from GitHub (or ``OVC_UPDATE_FEED``)."""
    try:
        with _open(_feed_url(), "application/vnd.github+json") as response:
            data = json.loads(response.read().decode("utf-8"))
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"Could not reach the update server: {exc}") from exc
    tag = data.get("tag_name") or ""
    if parse_version(tag) is None:
        raise UpdateError(f"The latest release has an unexpected tag: {tag!r}")
    assets = {
        a.get("name"): a.get("browser_download_url") for a in data.get("assets") or []
    }
    return {
        "version": tag.lstrip("v"),
        "tag": tag,
        "name": data.get("name") or tag,
        "release_url": data.get("html_url") or RELEASES_PAGE,
        "notes": (data.get("body") or "")[:4000],
        "published": data.get("published_at") or "",
        "installer_url": assets.get(INSTALLER_NAME),
        "checksum_url": assets.get(CHECKSUM_NAME),
    }


def check(force: bool = False) -> dict:
    """Compare the running version with the latest release.

    Never raises: problems are returned in ``error`` with ``available`` False.
    """
    kind = install_kind()
    result = {
        "enabled": checks_enabled(),
        "current": __version__,
        "latest": None,
        "available": False,
        "kind": kind,
        "release_url": RELEASES_PAGE,
        "download_url": DOWNLOAD_URL,
        "can_install": False,
        "notes": "",
        "error": None,
    }
    if not result["enabled"] and not force:
        return result
    try:
        latest = fetch_latest()
    except UpdateError as exc:
        result["error"] = str(exc)
        return result
    newer = parse_version(latest["version"]) > (parse_version(__version__) or (0,))
    result.update(
        latest=latest["version"],
        available=newer,
        release_url=latest["release_url"],
        notes=latest["notes"],
        download_url=latest["installer_url"] or DOWNLOAD_URL,
        installer_url=latest["installer_url"],
        checksum_url=latest["checksum_url"],
        can_install=bool(
            newer
            and kind == "installer"
            and latest["installer_url"]
            and latest["checksum_url"]
        ),
    )
    return result


def download_installer(installer_url: str, checksum_url: str, progress=None) -> Path:
    """Download the installer and check it against the published SHA-256."""
    try:
        with _open(checksum_url) as response:
            line = response.read().decode("ascii", "replace").strip()
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"Could not download the checksum: {exc}") from exc
    expected = line.split()[0].lower() if line else ""
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise UpdateError("The published checksum is not a SHA-256 value.")

    target = Path(tempfile.mkdtemp(prefix="ovc-update-")) / INSTALLER_NAME
    digest = hashlib.sha256()
    try:
        with _open(installer_url) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None and total:
                    progress(done / total)
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"Could not download the update: {exc}") from exc
    if digest.hexdigest() != expected:
        target.unlink(missing_ok=True)
        raise UpdateError(
            "The downloaded installer does not match its published checksum, so "
            "it was deleted and not run."
        )
    return target


def launch_installer(path: Path) -> None:
    """Start the installer: it upgrades OVC in place, then reopens it."""
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART"],
        creationflags=flags,
        close_fds=True,
    )
