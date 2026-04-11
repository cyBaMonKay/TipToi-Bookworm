"""Downloads .gme files from the official Ravensburger CDN with a progress bar."""

from pathlib import Path

import requests
from tqdm import tqdm


def download_gme(url: str, target_dir: Path) -> Path:
    """Download a .gme file to *target_dir* and return the resulting path."""
    filename = url.split("/")[-1]
    # Decode any percent-encoding for a friendlier filename
    filename = requests.utils.unquote(filename)
    dest = target_dir / filename

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
