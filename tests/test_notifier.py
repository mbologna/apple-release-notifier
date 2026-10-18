import os
import urllib.error

import pytest

from apple_release_notifier import is_relevant, load_last_guid, parse_feed, run

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
