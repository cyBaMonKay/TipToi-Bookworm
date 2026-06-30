# TipToi-Bookworm

A CLI tool to search and download TipToi® audio files (.gme) directly from the official Ravensburger servers.

## Features

- Scrapes the official [Ravensburger service page](https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien) for the product catalog
- Search by product name or article number
- Downloads .gme files exclusively from official Ravensburger domains (`ravensburger.cloud`, `ravensburger.de`, `ravensburger.info`) with validation enforced in both CLI and downloader
- Shows a progress bar during download
- Saves files to the current working directory

## Setup

Use your project virtual environment to keep the global Python environment clean.

From the repository root in Windows PowerShell:

```powershell
.\.venv\Scripts\python -m pip install -e .
```

For test-only setup (same dependency source as CI):

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

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

From the repository root in Windows PowerShell:

```powershell
python .\run.py
```

Safe check (does not start the interactive flow):

```powershell
python .\run.py --help
```

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
