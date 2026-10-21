# apple-release-notifier

[![CI](https://github.com/mbologna/apple-release-notifier/actions/workflows/ci.yml/badge.svg)](https://github.com/mbologna/apple-release-notifier/actions/workflows/ci.yml)

Sends a [Telegram](https://core.telegram.org/bots/api) message for every new
iOS and macOS release (betas included) in
[Apple's developer release feed](https://developer.apple.com/news/releases/).
It's built to run on a schedule, for example hourly as a Cloud Run job or a
Kubernetes CronJob.

Each run reads the feed and finds the newest item it saw last time, using a
guid stored in a state file. It then sends every newer iOS or macOS item,
oldest first. The very first run sends nothing and just records where the
feed is.

Progress is saved after every item. If sending fails, the run stops at that
item, and the next run picks up exactly there. A large batch of betas therefore
can't be lost, and isn't sent twice when a run times out halfway through.

## Configuration

| Variable | Required | Default | |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | yes | | Chat or channel to post to |
| `STATE_PATH` | no | `/state/last-guid.txt` | Where the last-seen guid is kept. Mount persistent storage here |

## Running

```sh
docker run --rm \
  -e TELEGRAM_BOT_TOKEN=123:abc -e TELEGRAM_CHAT_ID=-100123 \
  -v "$PWD/state:/state" \
  docker.io/mbologna/apple-release-notifier:1.0.1
```

Images are published to Docker Hub and to `ghcr.io/mbologna/apple-release-notifier`.

## Development

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Dependencies resolve only to releases at least 7 days old (`exclude-newer` in
`pyproject.toml`), and the image installs exactly what `uv.lock` pins. To take
a security fix released less than 7 days ago, add a temporary
`exclude-newer-package` override for that package under `[tool.uv]`, relock,
and remove the override once the release is 7 days old.
