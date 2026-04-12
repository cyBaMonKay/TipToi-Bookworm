"""Downloads .gme files from the official Ravensburger CDN with a progress bar."""

from pathlib import Path

import requests
from tqdm import tqdm


def download_gme(url: str, target_dir: Path) -> Path:
    """Download a .gme file to *target_dir* and return the resulting path."""
    filename = url.split("/")[-1]
    # Decode any percent-encoding for a friendlier filename
    filename = requests.utils.unquote(filename)
    # Strip to bare name to prevent path-traversal via encoded separators
    filename = Path(filename).name
    if not filename:
        raise ValueError("Could not derive a safe filename from URL")
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
