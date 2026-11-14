# apple-release-notifier

> **Archived (2026-11-14).** This project moved into a private repository
> next to the jobs that download the releases it announced. It no longer
> runs, and the code stays here for reference.

[![CI](https://github.com/mbologna/apple-release-notifier/actions/workflows/ci.yml/badge.svg)](https://github.com/mbologna/apple-release-notifier/actions/workflows/ci.yml)

Sends a [Telegram](https://core.telegram.org/bots/api) message for every new
iOS and macOS release (betas included) in
[Apple's developer release feed](https://developer.apple.com/news/releases/).

Each run reads the feed and finds the newest item it saw last time, using a
guid stored in a state file. It then sends every newer iOS or macOS item,
oldest first. The very first run sends nothing and just records where the
feed is.

Progress is saved after every item. If sending fails, the run stops at that
item, and the next run picks up exactly there. A large batch of betas therefore
can't be lost, and isn't sent twice when a run times out halfway through.

## How it runs

The [Notify workflow](.github/workflows/notify.yml) runs the script with
GitHub Actions, with the dependencies `uv.lock` pins:

- **Schedule:** hourly at :30 from 12:30 to 22:30 UTC, which covers
  14:30–23:30 in Europe/Rome in both winter and summer. Runs never overlap.
- **State:** the last-seen guid is kept in the Actions cache. Each run
  restores the newest copy and saves its own under a new key. If the cache
  is ever lost, the next run treats the feed as already seen, so nothing is
  sent twice.
- **Secrets:** the repository secrets `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID`. Until both are set, runs skip with a notice.
- **Failures:** a failed run sends GitHub's failed-workflow email. A feed that
  can't be fetched or parsed isn't a failure: the next run retries.

To start from a known item (for example when moving the state from another
host), run the workflow manually with `seed_guid` set to that item's guid. The
run overwrites the saved state with it, then sends everything newer.

GitHub disables a public repo's scheduled workflows after 60 days without
activity in the repository. Renovate's commits keep this one active; if it
is ever disabled, re-enable it from the Actions tab.

## Configuration

| Variable | Required | Default | |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | yes | | Chat or channel to post to |
| `STATE_PATH` | no | `/state/last-guid.txt` | Where the last-seen guid is kept |

## Running locally

```sh
TELEGRAM_BOT_TOKEN=123:abc TELEGRAM_CHAT_ID=-100123 STATE_PATH=state/last-guid.txt \
  uv run apple-release-notifier
```

## Development

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Dependencies resolve only to releases at least 7 days old (`exclude-newer` in
`pyproject.toml`), and the workflow installs exactly what `uv.lock` pins. To
take a security fix released less than 7 days ago, add a temporary
`exclude-newer-package` override for that package under `[tool.uv]`, relock,
and remove the override once the release is 7 days old.
