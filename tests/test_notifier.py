import io
import json
import os
import runpy
import urllib.error

import pytest

import apple_release_notifier
from apple_release_notifier import fetch_feed, is_relevant, load_last_guid, parse_feed, run, telegram_sender

FEED = b"""<?xml version="1.0"?>
<rss><channel>
  <item><title>macOS Tahoe 26.2 beta 3 (25C5048a)</title><link>https://e.com/4</link><guid>g4</guid></item>
  <item><title>Xcode 26.2 beta 3</title><link>https://e.com/3</link><guid>g3</guid></item>
  <item><title>iOS 26.1 (23B85)</title><link>https://e.com/2</link><guid>g2</guid></item>
  <item><title>watchOS 26.1</title><link>https://e.com/1</link><guid>g1</guid></item>
  <item><title></title><link>https://e.com/0</link><guid>g0</guid></item>
</channel></rss>"""


@pytest.fixture
def items():
    return parse_feed(FEED)


@pytest.fixture
def state(tmp_path):
    return str(tmp_path / "state" / "last-guid.txt")


def write_state(path, guid):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(guid)


class Recorder:
    def __init__(self, fail_on=None):
        self.sent = []
        self.fail_on = fail_on

    def __call__(self, title, link):
        if title == self.fail_on:
            raise urllib.error.URLError("boom")
        self.sent.append(title)


def test_parse_feed_skips_items_without_title(items):
    assert [it["guid"] for it in items] == ["g4", "g3", "g2", "g1"]


def test_parse_feed_falls_back_to_link_for_guid():
    xml = b"<rss><channel><item><title>iOS 1</title><link>https://e.com/x</link></item></channel></rss>"
    assert parse_feed(xml)[0]["guid"] == "https://e.com/x"


@pytest.mark.parametrize(
    "title,expected",
    [
        ("iOS 26.1", True),
        ("macOS Tahoe 26.2", True),
        ("iPadOS 26.1", False),
        ("Xcode 26", False),
        ("watchOS 26", False),
    ],
)
def test_is_relevant(title, expected):
    assert is_relevant(title) is expected


def test_first_run_sends_nothing_and_saves_newest(items, state):
    send = Recorder()
    assert run(items, state, send) == 0
    assert send.sent == []
    assert load_last_guid(state) == "g4"


def test_sends_relevant_new_items_oldest_first(items, state):
    write_state(state, "g1")
    send = Recorder()
    assert run(items, state, send) == 2
    assert send.sent == ["iOS 26.1 (23B85)", "macOS Tahoe 26.2 beta 3 (25C5048a)"]
    assert load_last_guid(state) == "g4"


def test_unknown_watermark_treats_whole_feed_as_new(items, state):
    write_state(state, "gone")
    send = Recorder()
    run(items, state, send)
    assert send.sent == ["iOS 26.1 (23B85)", "macOS Tahoe 26.2 beta 3 (25C5048a)"]


def test_failure_stops_and_keeps_the_watermark_before_it(items, state):
    write_state(state, "g1")
    send = Recorder(fail_on="macOS Tahoe 26.2 beta 3 (25C5048a)")
    assert run(items, state, send) == 1
    # g2 (iOS) and g3 (Xcode, skipped) are done; g4 failed, so the next run resumes there.
    assert load_last_guid(state) == "g3"
    resumed = Recorder()
    run(items, state, resumed)
    assert resumed.sent == ["macOS Tahoe 26.2 beta 3 (25C5048a)"]


def test_empty_feed_is_a_no_op(state):
    assert run([], state, Recorder()) == 0
    assert load_last_guid(state) == ""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_telegram_sender_posts_escaped_html(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        return FakeResponse(b"{}")

    monkeypatch.setattr(apple_release_notifier.urllib.request, "urlopen", fake_urlopen)
    telegram_sender("TOKEN", "42")("iOS 26.1 <beta>", "https://e.com/?a=1&b=2")
    ((req, timeout),) = calls
    assert req.full_url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert timeout == 15
    payload = json.loads(req.data)
    assert payload == {
        "chat_id": "42",
        "text": "<b>iOS 26.1 &lt;beta&gt;</b>\nhttps://e.com/?a=1&amp;b=2",
        "parse_mode": "HTML",
    }


def test_fetch_feed_parses_the_response(monkeypatch):
    monkeypatch.setattr(apple_release_notifier.urllib.request, "urlopen", lambda req, timeout: FakeResponse(FEED))
    assert [it["guid"] for it in fetch_feed()] == ["g4", "g3", "g2", "g1"]


@pytest.fixture
def env(monkeypatch, state):
    monkeypatch.setenv("STATE_PATH", state)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")


def test_main_sends_new_items(monkeypatch, env, items, state):
    write_state(state, "g2")
    sent = Recorder()
    monkeypatch.setattr(apple_release_notifier, "fetch_feed", lambda: items)
    monkeypatch.setattr(apple_release_notifier, "telegram_sender", lambda token, chat: sent)
    apple_release_notifier.main()
    assert sent.sent == ["macOS Tahoe 26.2 beta 3 (25C5048a)"]
    assert load_last_guid(state) == "g4"


def test_main_feed_failure_is_not_fatal(monkeypatch, env, state, capsys):
    def broken():
        raise urllib.error.URLError("down")

    monkeypatch.setattr(apple_release_notifier, "fetch_feed", broken)
    apple_release_notifier.main()
    assert "feed fetch/parse failed" in capsys.readouterr().err
    assert load_last_guid(state) == ""


def test_module_entry_point_runs_main(monkeypatch):
    called = []
    monkeypatch.setattr(apple_release_notifier, "main", lambda: called.append(True))
    runpy.run_module("apple_release_notifier", run_name="__main__")
    assert called == [True]
