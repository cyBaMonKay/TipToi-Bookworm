"""Downloads .gme files from the official Ravensburger CDN with a progress bar."""

import re
from pathlib import Path
from urllib.parse import urlsplit

import requests
from tqdm import tqdm

ALLOWED_HOSTS = ("ravensburger.cloud", "ravensburger.de", "ravensburger.info")

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


def is_official_source(url: str) -> bool:
    """Return True if *url* is hosted on an official Ravensburger domain."""
    host = urlsplit(url).hostname or ""
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def download_gme(url: str, target_dir: Path) -> Path:
    """Download a .gme file to *target_dir* and return the resulting path."""
    if not is_official_source(url):
        raise ValueError("Refusing download from non-official host")

    filename = _derive_safe_filename(url)
    dest = (target_dir / filename).resolve()
    if not str(dest).startswith(str(target_dir.resolve())):
        raise ValueError(f"Refusing to write outside target directory: {dest}")

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(dest, "wb") as f, tqdm(
        desc=filename,
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            written = f.write(chunk)
            bar.update(written)

    return dest
