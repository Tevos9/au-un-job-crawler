# AU/UN Job Crawler

A lightweight job alert bot that monitors UN Careers RSS and AU Jobs website postings, filters them by keywords, and sends Telegram notifications for new matching jobs.

## Features

- Fetches job listings from the UN Careers RSS feed
- Scrapes AU Jobs listings using Playwright
- Filters jobs using configurable keywords
- Tracks seen jobs in SQLite to avoid duplicate alerts
- Sends alerts to Telegram with individual messages or a digest
- Supports `--dry-run` and `--reset` modes

## Requirements

- Python 3.12+
- `feedparser`
- `requests`
- `playwright`
- Telegram bot credentials

## Setup

Install the Python dependencies and Playwright browser:

```bash
python -m pip install feedparser requests playwright
playwright install chromium
```

## Configuration

Set the following environment variables before running:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Local Development

Create a `.env` file (never commit this):

```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Then load it before running:

```bash
# On Linux/Mac
export $(cat .env | xargs)
python crawler.py

# On Windows PowerShell
$env:TELEGRAM_BOT_TOKEN = "your_token_here"
$env:TELEGRAM_CHAT_ID = "your_chat_id_here"
python crawler.py
```

### GitHub Actions (Automated)

For automatic periodic execution on GitHub:

1. Go to your GitHub repository settings
2. Navigate to **Secrets and variables → Actions**
3. Create two secrets:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHAT_ID`: Your Telegram chat/channel ID

4. The workflow at `.github/workflows/job-alerts.yml` will run automatically every 6 hours

The secrets are **never exposed** in logs or the repository code. GitHub Actions injects them safely at runtime.

## Usage

```bash
python crawler.py
python crawler.py --dry-run
python crawler.py --reset
```

## Notes

- The script stores seen jobs in `jobs_seen.db`
- Keywords are configured in `crawler.py`
- Use `--dry-run` to test without sending messages or saving state
