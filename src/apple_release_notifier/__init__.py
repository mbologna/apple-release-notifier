"""Telegram notifications for new iOS and macOS releases.

Reads Apple's developer release feed, keeps the guid of the newest item it
has seen in a state file, and sends every newer iOS or macOS release to a
Telegram chat, oldest first.
"""

import html
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://developer.apple.com/news/releases/rss/releases.rss"
UA = {"User-Agent": "apple-release-notifier/1.0"}


def telegram_sender(bot_token, chat_id):
    """Returns send(title, link). It raises urllib.error.URLError on failure."""

    def send(title, link):
        payload = {
            "chat_id": chat_id,
            "text": f"<b>{html.escape(title)}</b>\n{html.escape(link)}",
            "parse_mode": "HTML",
        }
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **UA},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()

    return send


def parse_feed(xml_bytes):
    """Feed items, newest first, as dicts with title, link and guid."""
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        if title and guid:
            items.append({"title": title, "link": link, "guid": guid})
    return items


def fetch_feed(url=FEED_URL):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return parse_feed(r.read())


def is_relevant(title):
    return title.startswith("iOS ") or title.startswith("macOS ")


def load_last_guid(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_last_guid(path, guid):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(guid)


def run(items, state_path, send):
    """Sends the relevant items newer than the watermark. Returns the count."""
    if not items:
        print("feed returned no items: nothing to do")
        return 0

    last_guid = load_last_guid(state_path)
    if last_guid:
        idx = next((i for i, it in enumerate(items) if it["guid"] == last_guid), len(items))
        new_items = items[:idx]
    else:
        print("no prior state: treating the whole feed as already seen (first run)")
        new_items = []

    sent = 0
    for it in reversed(new_items):  # oldest first
        if is_relevant(it["title"]):
            print(f"notifying: {it['title']}")
            try:
                send(it["title"], it["link"])
            except (urllib.error.URLError, OSError) as e:
                # Stop rather than skip: the watermark is still at the previous
                # item, so the next run resumes exactly here.
                print(f"notify failed for {it['title']}: {e}; stopping, will resume next run", file=sys.stderr)
                return sent
            sent += 1
        # Persist after every item, not once at the end: a large batch (Apple
        # ships betas in bulk) can outlast the job's timeout, and saving only at
        # the end made each timed-out run re-send the same batch.
        save_last_guid(state_path, it["guid"])

    save_last_guid(state_path, items[0]["guid"])
    print(f"Done: {sent} notification(s) sent.")
    return sent


def main():
    state_path = os.environ.get("STATE_PATH", "/state/last-guid.txt")
    send = telegram_sender(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"])
    try:
        items = fetch_feed()
    except (urllib.error.URLError, OSError, ET.ParseError) as e:
        # A transient feed problem is not a job failure: the next run retries.
        print(f"feed fetch/parse failed: {e}", file=sys.stderr)
        return
    run(items, state_path, send)
