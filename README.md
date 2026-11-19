# TipToi-Bookworm

A script-only tool to search and download TipToi® audio files (.gme) directly from the official Ravensburger servers.

## Features

- Scrapes the official [Ravensburger service page](https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien) for the product catalog
- Search by product name or article number
- Downloads .gme files exclusively over HTTPS from official Ravensburger domains (`ravensburger.cloud`, `ravensburger.de`, `ravensburger.info`): the interactive runtime prechecks the host, and the downloader enforces HTTPS plus the host allowlist on the initial URL and every redirect hop
- Shows a progress bar during download with elapsed time, estimated time remaining, and transfer rate
- Saves files to the current working directory

Article-number matching preserves leading zeros and recognizes complete five-digit
numbers. Numbers in a download link's text or URL take priority over surrounding
text. If both the link and its surrounding context lack a number, a unique
page-title number is used only when the page has one distinct download URL. Conflicting numbers are left
unassigned rather than guessed, and numbers from another download are not reused.

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

Install the pinned runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

If `.venv` already exists and is activated, run the same commands via that interpreter.


## Usage

```bash
python bookworm.py
```

The script will:

1. Fetch the latest product catalog from Ravensburger
2. Prompt you to enter a search term
3. Display matching results
4. Let you pick one and confirm the download

Safe check (does not start the interactive flow):

```bash
python bookworm.py --help
```

Launcher exit code contract:

- `0`: success (including `--help`)
- `130`: interrupted (`Ctrl+C`)
- `1`: launcher or runtime startup failure

For defense in depth, URL host validation is enforced in two layers:

1. **Runtime precheck (`bookworm`)**: warns and skips entries that are not hosted on official Ravensburger domains, showing only the rejected host instead of the full URL.
2. **Downloader enforcement (`bookworm.downloader.download_gme`)**: rejects non-official hosts and non-HTTPS URLs with a `ValueError`, even when called directly outside the interactive runtime flow.

Catalog links wrapped by Outlook SafeLinks (`*.safelinks.protection.outlook.com`) are decoded locally to their `url` target; the wrapper is never requested, and Outlook is not an allowed download host. The decoded target then passes through the same checks as any other link. Wrappers without exactly one absolute HTTP(S) target (including wrappers of another SafeLinks URL) are skipped. A decoded target that another link on the same page already provides is listed only once.

The downloader follows redirects itself instead of letting `requests` follow them automatically. Each redirect target (relative `Location` headers are resolved against the current URL) must pass the same HTTPS + official-host check **before** it is requested, so a disallowed host is never contacted and HTTPS cannot be downgraded to plaintext HTTP. At most 5 redirects are followed; more raise `requests.TooManyRedirects`. A rejected download leaves no partial file and keeps any existing file with the same name.

Allowed host suffixes:

- `ravensburger.cloud`
- `ravensburger.de`
- `ravensburger.info`

Subdomains of these hosts are allowed (for example `cdn.ravensburger.de`). Host checks are case-insensitive, reject malformed URLs, and do not treat trailing-dot hostnames as official.

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
