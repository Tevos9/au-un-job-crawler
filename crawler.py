"""
AU/UN Job Alert Bot

Monitors UN Careers RSS and AU Jobs website for new postings,
filters by keyword, and sends Telegram alerts.

Requirements:
pip install feedparser requests playwright
playwright install chromium

Environment Variables:
TELEGRAM_BOT_TOKEN  - Your Telegram bot token
TELEGRAM_CHAT_ID    - Your Telegram chat/channel ID

Usage:
python crawler.py              # Normal run
python crawler.py --dry-run    # Test without saving state or sending messages
python crawler.py --reset      # Clear seen jobs and start fresh
"""

import argparse
import html
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

import feedparser
import requests
from playwright.sync_api import sync_playwright

# ====================== CONFIG ======================

UN_RSS_URL = "https://careers.un.org/jobfeed?isPage=true&language=en"

# Add more UN-system RSS feeds here easily
EXTRA_RSS_SOURCES = [
    # ("UNDP", "https://jobs.undp.org/cj_view_jobs.cfm?rss"),
    # ("UNHCR", "https://www.unhcr.org/careers/rss"),
]

# Keywords to match against title + description + link (case-insensitive)
# Leave empty to receive ALL jobs
KEYWORDS = [
    "Nigeria",
    "Abuja",
    "Africa",
    "Ethiopia",
    "Internship",
    "Consultant",
    "Volunteer",
    "P2",
    "P3",
]

# Telegram config
TELEGRAM_MAX_CHARS = 4096
TELEGRAM_RATE_LIMIT_SECONDS = 1

# How many seen job IDs to keep per source (prevents DB bloat)
MAX_SEEN_PER_SOURCE = 2000

# DB file for seen jobs
DB_FILE = "jobs_seen.db"

# Retry config
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ====================== LOGGING ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("job_alert.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ====================== DATABASE (replaces JSON) ======================

def init_db() -> sqlite3.Connection:
    """Initialize SQLite DB and create table if needed."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            source TEXT NOT NULL,
            job_id TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (source, job_id)
        )
        """
    )
    conn.commit()
    return conn


def is_seen(conn: sqlite3.Connection, source: str, job_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen_jobs WHERE source=? AND job_id=?", (source, job_id)
    ).fetchone()
    return row is not None


def mark_seen(conn: sqlite3.Connection, source: str, job_id: str):
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs (source, job_id, seen_at) VALUES (?, ?, ?)",
        (source, job_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


def prune_old_entries(conn: sqlite3.Connection):
    """Keep only the most recent MAX_SEEN_PER_SOURCE entries per source."""
    sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM seen_jobs")]
    for source in sources:
        count = conn.execute(
            "SELECT COUNT(*) FROM seen_jobs WHERE source=?", (source,)
        ).fetchone()[0]
        if count > MAX_SEEN_PER_SOURCE:
            excess = count - MAX_SEEN_PER_SOURCE
            conn.execute(
                """
                DELETE FROM seen_jobs WHERE rowid IN (
                    SELECT rowid FROM seen_jobs WHERE source=?
                    ORDER BY seen_at ASC LIMIT ?
                )
                """,
                (source, excess),
            )
            log.info(f"Pruned {excess} old entries for source '{source}'")
    conn.commit()


def reset_db(conn: sqlite3.Connection):
    conn.execute("DELETE FROM seen_jobs")
    conn.commit()
    log.info("Seen jobs database cleared.")

# ====================== TELEGRAM ======================

def send_telegram(message: str, dry_run: bool = False):
    """Send a Telegram message, with length guard and dry-run support."""
    if dry_run:
        log.info(f"[DRY RUN] Would send Telegram message:\n{message}")
        return

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set!")
        return

    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[: TELEGRAM_MAX_CHARS - 20] + "\n... (truncated)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            log.info("Telegram message sent.")
            return
        except Exception as e:
            log.warning(f"Telegram send attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    log.error("All Telegram send attempts failed.")


def escape_telegram_text(text: str, quote: bool = False) -> str:
    return html.escape(text or "", quote=quote)


def send_jobs_as_individual_messages(jobs: list, dry_run: bool = False):
    """Send one Telegram message per job for rich link previews.
    Falls back to a batch summary if there are many jobs.
    """
    if len(jobs) > 15:
        header = (
            f"<b>🔔 {len(jobs)} New AU/UN Jobs ({datetime.now().strftime('%Y-%m-%d')})</b>\n\n"
        )
        body = ""
        for job in jobs[:20]:
            body += (
                f"• <b>{escape_telegram_text(job['source'])}</b>: "
                f"<a href='{escape_telegram_text(job['link'], quote=True)}'>"
                f"{escape_telegram_text(job['title'])}</a>\n"
            )
        if len(jobs) > 20:
            body += f"\n…and {len(jobs) - 20} more. Check portals for full list."
        send_telegram(header + body, dry_run=dry_run)
        return

    for job in jobs:
        source_emoji = "🇺🇳" if job["source"] == "UN" else "🌍"
        source_text = escape_telegram_text(job["source"])
        title_text = escape_telegram_text(job["title"])
        link_text = escape_telegram_text(job["link"], quote=True)
        pub = (
            f"\n📅 {escape_telegram_text(job.get('published', ''))}"
            if job.get("published")
            else ""
        )
        desc = (
            f"\n📝 {escape_telegram_text(job.get('description', '')[:200])}..."
            if job.get("description")
            else ""
        )
        msg = (
            f"{source_emoji} <b>[{source_text}] {title_text}</b>"
            f"{pub}"
            f"{desc}"
            f"\n🔗 <a href='{link_text}'>View Job</a>"
        )
        send_telegram(msg, dry_run=dry_run)
        time.sleep(TELEGRAM_RATE_LIMIT_SECONDS)

# ====================== JOB SOURCES ======================

def get_rss_jobs(source_name: str, rss_url: str) -> list:
    """Generic RSS job fetcher with retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"Fetching {source_name} RSS (attempt {attempt})...")
            feed = feedparser.parse(rss_url)
            if feed.bozo and not feed.entries:
                raise ValueError(f"Feed parse error: {feed.bozo_exception}")
            jobs = []
            for entry in feed.entries:
                title = entry.get("title", "No Title").strip()
                link = entry.get("link", "")
                published = entry.get("published", "")
                job_id = entry.get("id", link)
                description = entry.get("summary", "")
                jobs.append(
                    {
                        "source": source_name,
                        "id": job_id,
                        "title": title,
                        "link": link,
                        "published": published,
                        "description": description,
                    }
                )
            log.info(f"Found {len(jobs)} {source_name} jobs from RSS.")
            return jobs
        except Exception as e:
            log.warning(f"{source_name} RSS attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    log.error(f"Failed to fetch {source_name} RSS after {MAX_RETRIES} attempts.")
    return []


def get_au_jobs() -> list:
    """Scrape AU Jobs site using Playwright with safety guards."""
    jobs = []
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"Scraping AU Jobs (attempt {attempt})...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(
                    "https://jobs.au.int/",
                    wait_until="networkidle",
                    timeout=60000,
                )

                try:
                    page.wait_for_selector("main, #content, .jobs-list", timeout=10000)
                except Exception:
                    log.warning("Could not find main content container, using full page.")

                page.wait_for_selector("a[href*='/job/']", timeout=30000)
                job_elements = page.query_selector_all("a[href*='/job/']")

                seen_links = set()
                for el in job_elements:
                    href = el.get_attribute("href") or ""
                    if not href or href == "/" or "job" not in href:
                        continue

                    full_link = (
                        "https://jobs.au.int" + href if href.startswith("/") else href
                    )
                    if full_link in seen_links:
                        continue
                    seen_links.add(full_link)

                    title_el = el.query_selector("h3, h2, .job-title, strong")
                    title = (
                        title_el.inner_text().strip() if title_el else el.inner_text().strip()
                    ) or "No Title"

                    jobs.append(
                        {
                            "source": "AU",
                            "id": full_link,
                            "title": title,
                            "link": full_link,
                            "description": "",
                        }
                    )

                browser.close()
            log.info(f"Found {len(jobs)} AU jobs from website.")
            return jobs
        except Exception as e:
            log.warning(f"AU Jobs scrape attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    log.error(f"Failed to scrape AU Jobs after {MAX_RETRIES} attempts.")
    return []

# ====================== FILTER ======================

def filter_jobs(jobs: list) -> list:
    """Filter jobs by KEYWORDS across title, description, and link."""
    if not KEYWORDS:
        return jobs
    matched = []
    for job in jobs:
        searchable = " ".join(
            [
                job.get("title", ""),
                job.get("description", ""),
                job.get("link", ""),
            ]
        ).lower()
        if any(kw.lower() in searchable for kw in KEYWORDS):
            matched.append(job)
    return matched

# ====================== MAIN ======================

def parse_args():
    parser = argparse.ArgumentParser(description="AU/UN Job Alert Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving state or sending Telegram messages",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all seen jobs and start fresh",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    conn = init_db()

    if args.reset:
        reset_db(conn)

    if args.dry_run:
        log.info("=== DRY RUN MODE - No messages will be sent, no state saved ===")

    all_new_jobs = []

    un_jobs = get_rss_jobs("UN", UN_RSS_URL)
    for job in un_jobs:
        if not is_seen(conn, "UN", job["id"]):
            all_new_jobs.append(job)
            if not args.dry_run:
                mark_seen(conn, "UN", job["id"])

    for source_name, rss_url in EXTRA_RSS_SOURCES:
        extra_jobs = get_rss_jobs(source_name, rss_url)
        for job in extra_jobs:
            if not is_seen(conn, source_name, job["id"]):
                all_new_jobs.append(job)
                if not args.dry_run:
                    mark_seen(conn, source_name, job["id"])

    au_jobs = get_au_jobs()
    for job in au_jobs:
        if not is_seen(conn, "AU", job["id"]):
            all_new_jobs.append(job)
            if not args.dry_run:
                mark_seen(conn, "AU", job["id"])

    new_jobs = filter_jobs(all_new_jobs)
    log.info(
        f"Total new jobs before filter: {len(all_new_jobs)} | After filter: {len(new_jobs)}"
    )

    if new_jobs:
        log.info(f"Sending alerts for {len(new_jobs)} new job(s)...")
        send_jobs_as_individual_messages(new_jobs, dry_run=args.dry_run)
    else:
        log.info("No new matching jobs found.")

    if not args.dry_run:
        prune_old_entries(conn)
        conn.commit()

    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
