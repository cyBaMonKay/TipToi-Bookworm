"""Run bookworm CLI from repository root without installation."""

from __future__ import annotations

import sys
from pathlib import Path

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INTERRUPTED = 130


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _normalize_exit_code(code: object) -> int:
    if code is None:
        return EXIT_OK
    if isinstance(code, int):
        return code
    return EXIT_FAILURE


def main() -> int:
    _ensure_src_on_path()

    # Keep a safe help mode for uninstalled repo execution.
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("TipToi-Bookworm repository launcher")
        print("Run the interactive CLI directly from this checkout.")
        print()
        print("Usage:")
        print("  python run.py [--help]")
        print()
        print("Options:")
        print("  -h, --help    Show this help message and exit")
        print()
        print("Exit codes:")
        print("  0   success (including --help)")
        print("  130 interrupted (Ctrl+C)")
        print("  1   launcher or CLI startup failure")
        return EXIT_OK

    from bookworm.cli import main as cli_main

    try:
        cli_result = cli_main()
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except SystemExit as exc:
        return _normalize_exit_code(exc.code)

    if isinstance(cli_result, int):
        return cli_result
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
