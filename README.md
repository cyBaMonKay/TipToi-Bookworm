# TipToi-Bookworm

A CLI tool to search and download TipToi® audio files (.gme) directly from the official Ravensburger servers.

## Features

- Scrapes the official [Ravensburger service page](https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien) for the product catalog
- Search by product name or article number
- Downloads .gme files exclusively from official Ravensburger domains (`ravensburger.cloud`)
- Shows a progress bar during download
- Saves files to the current working directory

## Setup

```bash
pip install -e .
```

## Run without installation

From the repository root in Windows PowerShell:

```powershell
python .\run.py
```

Safe check (does not start the interactive flow):

```powershell
python .\run.py --help
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

## Disclaimer

TipToi-Bookworm is neither offered nor supported by Ravensburger. tiptoi® is a registered trademark of Ravensburger.
