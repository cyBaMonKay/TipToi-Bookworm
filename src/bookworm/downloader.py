"""Downloads .gme files from the official Ravensburger CDN with a progress bar."""

import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from tqdm import tqdm

ALLOWED_HOSTS = ("ravensburger.cloud", "ravensburger.de", "ravensburger.info")
ALLOWED_SCHEME = "https"
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = 30
STREAM_CHUNK_SIZE = 8192
PROGRESS_UNIT_DIVISOR = 1024
PROGRESS_BAR_FORMAT = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def _cleanup_partial_download(temp_path: Path, fd: int | None = None) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass

    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass


def _sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = "".join(ch if ord(ch) >= 32 else "_" for ch in filename)
    filename = filename.strip(" .")
    if not filename:
        return ""

    stem, dot, suffix = filename.partition(".")
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    return f"{stem}{dot}{suffix}" if dot else stem


def _derive_safe_filename(url: str) -> str:
    path = urlsplit(url).path
    filename = Path(path).name
    filename = requests.utils.unquote(filename)
    filename = Path(filename).name
    filename = _sanitize_filename(filename)
    return filename or "download.gme"


def _validate_gme_filename(filename: str) -> None:
    if Path(filename).suffix.lower() != ".gme":
        raise ValueError(f"Refusing download: expected a .gme file, got {filename!r}")


def is_official_source(url: str) -> bool:
    """Return True if *url* is hosted on an official Ravensburger domain."""
    host = urlsplit(url).hostname or ""
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def _require_allowed_url(url: str, refusal: str) -> None:
    parts = urlsplit(url)
    if not is_official_source(url):
        raise ValueError(f"{refusal} non-official host: {parts.hostname or url}")
    if parts.scheme != ALLOWED_SCHEME:
        raise ValueError(f"{refusal} non-HTTPS URL: {url}")


def _open_download_stream(session: requests.Session, url: str) -> requests.Response:
    """GET *url*, following at most MAX_REDIRECTS redirects manually.

    Each redirect target is validated before it is requested, so a disallowed
    host or scheme is never contacted.
    """
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        resp = session.get(
            current_url, stream=True, timeout=REQUEST_TIMEOUT, allow_redirects=False
        )
        location = session.get_redirect_target(resp)
        if location is None:
            return resp

        resp.close()
        current_url = urljoin(current_url, location)
        _require_allowed_url(current_url, "Refusing redirect to")

    raise requests.TooManyRedirects(f"Exceeded {MAX_REDIRECTS} redirects")


def download_gme(url: str, target_dir: Path) -> Path:
    """Download a .gme file to *target_dir* and return the resulting path.

    The URL and every redirect target must use HTTPS on an official host.
    """
    _require_allowed_url(url, "Refusing download from")

    filename = _derive_safe_filename(url)
    _validate_gme_filename(filename)
    dest = (target_dir / filename).resolve()
    if not str(dest).startswith(str(target_dir.resolve())):
        raise ValueError(f"Refusing to write outside target directory: {dest}")

    target_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_path_str = tempfile.mkstemp(
        dir=str(target_dir.resolve()),
        prefix=f".{filename}.",
        suffix=".part",
    )
    temp_path = Path(temp_path_str)
    fd_to_close: int | None = fd
    cleanup_needed = True

    try:
        with requests.Session() as session, _open_download_stream(session, url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))

            with os.fdopen(fd_to_close, "wb") as f, tqdm(
                desc=filename,
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=PROGRESS_UNIT_DIVISOR,
                bar_format=PROGRESS_BAR_FORMAT,
            ) as bar:
                fd_to_close = None
                for chunk in resp.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                    written = f.write(chunk)
                    bar.update(written)

        os.replace(temp_path, dest)
        cleanup_needed = False
    except requests.RequestException:
        _cleanup_partial_download(temp_path, fd_to_close)
        cleanup_needed = False
        raise
    except OSError:
        _cleanup_partial_download(temp_path, fd_to_close)
        cleanup_needed = False
        raise
    finally:
        if cleanup_needed:
            _cleanup_partial_download(temp_path, fd_to_close)

    return dest
