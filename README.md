# TipToi-Bookworm

A CLI tool to search and download TipToi® audio files (.gme) directly from the official Ravensburger servers.

## Features

- Scrapes the official [Ravensburger service page](https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien) for the product catalog
- Search by product name or article number
- Downloads .gme files exclusively from official Ravensburger domains (`ravensburger.cloud`, `ravensburger.de`, `ravensburger.info`) with validation enforced in both CLI and downloader
- Shows a progress bar during download
- Saves files to the current working directory

## Setup

Use a project virtual environment to keep your global Python installation clean.

Create and activate a venv from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install in editable mode for day-to-day local use:

```bash
python -m pip install -e .
```

Install from pinned requirements for test parity with CI:

```bash
python -m pip install -r requirements.txt
```

Dependency strategy:

- `pyproject.toml` declares runtime dependency ranges for package installs.
- `requirements.txt` pins exact versions for reproducible test/CI environments.

If `.venv` already exists and is activated, run the same commands via that interpreter.


## Usage

```bash
bookworm
```

The CLI will:

1. Fetch the latest product catalog from Ravensburger
2. Prompt you to enter a search term
3. Display matching results
4. Let you pick one and confirm the download

## Download source validation

For defense in depth, URL host validation is enforced in two layers:

1. **CLI precheck (`bookworm.cli`)**: warns and skips entries that are not hosted on official Ravensburger domains.
2. **Downloader enforcement (`bookworm.downloader.download_gme`)**: rejects non-official hosts with a `ValueError`, even when called directly outside the CLI flow.

Allowed host suffixes:

- `ravensburger.cloud`
- `ravensburger.de`
- `ravensburger.info`

Subdomains of these hosts are allowed (for example `cdn.ravensburger.de`). Host checks are case-insensitive, reject malformed URLs, and do not treat trailing-dot hostnames as official.

## Run without installation

From the repository root:

```bash
python run.py
```

Safe check (does not start the interactive flow):

```bash
python run.py --help
```

Launcher exit code contract:

- `0`: success (including `--help`)
- `130`: interrupted (`Ctrl+C`)
- `1`: launcher or CLI startup failure

## Tests (canonical command)

From the repository root, run tests with the virtual environment interpreter:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
```

Required setup (clean checkout):

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

CI installs dependencies from requirements.txt and runs the same unittest command.

## Disclaimer

TipToi-Bookworm is neither offered nor supported by Ravensburger. tiptoi® is a registered trademark of Ravensburger.
