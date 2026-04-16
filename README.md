# AutoTeam Local Fork

This repository is a heavily customized fork of
[`cnitlrt/AutoTeam`](https://github.com/cnitlrt/AutoTeam).

It started from the upstream project, but the local workflow, UI, and automation
behavior have diverged enough that this repo is now maintained as an
independent fork.

## Fork Notes

- The dashboard and shell UX were reworked for daily operator use.
- Team member loading now prefers cache and manual refresh instead of fetching on
  every page visit.
- "Sync accounts" and quota refresh were split so account-state sync no longer
  forces an immediate quota refresh.
- The console restores a local snapshot on reload so the UI appears quickly
  before background refresh finishes.
- Browser automation can run headless with `PLAYWRIGHT_HEADLESS=1`, which is
  especially useful on Windows.

## What This Repo Is For

AutoTeam is used to manage a pool of ChatGPT Team accounts, related auth files,
and supporting operator workflows from a web console.

Main areas in this fork:

- Account pool and status overview
- Team member inspection and manual refresh
- Account sync and CPA sync operations
- OAuth / Codex auth handling
- Task history and operator logs

## Quick Start

### Backend

```bash
uv sync
uv run playwright install chromium
uv run autoteam api
```

Then open `http://localhost:8787`.

### Frontend

```bash
cd web
npm ci
npm run build
```

## Configuration

Important local configuration lives in `.env`.

Useful variables in this fork:

- `API_KEY`: API access key for the web console
- `CPA_URL` / `CPA_KEY`: CPA integration settings
- `PLAYWRIGHT_HEADLESS=1`: run browser automation without popping visible
  browser windows

See `.env.example` for the current template.

## CI

GitHub Actions in this fork run a simple CI pipeline:

- Python syntax validation
- Frontend production build

This keeps the checks easy to understand and avoids style-only failures caused
by auto-format hooks running inside CI.

## Upstream

Original upstream repository:

- https://github.com/cnitlrt/AutoTeam

This fork keeps the upstream remote as `upstream` so changes can still be
reviewed or cherry-picked when needed.
