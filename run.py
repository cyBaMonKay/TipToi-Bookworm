"""Run bookworm CLI from repository root without installation."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def main() -> int:
    _ensure_src_on_path()

    # Keep a safe help mode for uninstalled repo execution.
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("TipToi-Bookworm (repo launcher)")
        print("Run interactive CLI from repository without installation.")
        print()
        print("Usage:")
        print("  python run.py")
        print()
        print("Options:")
        print("  -h, --help    Show this help message and exit")
        return 0

    from bookworm.cli import main as cli_main

    cli_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
