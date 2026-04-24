# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

AutoTeam is a ChatGPT Team account rotation and authentication sync tool. It auto-registers accounts via CloudMail temporary emails + Playwright browser automation, obtains Codex OAuth tokens, rotates Team seats based on quota, and bidirectionally syncs auth files with CLIProxyAPI (CPA).

## Tech Stack

- **Backend:** Python 3.10+ (currently 3.13), FastAPI, Playwright (Chromium), Rich
- **Frontend:** Vue 3 SPA + Vite + Tailwind CSS (dark theme, zh-CN)
- **Package Manager:** `uv` (Python), `npm` (frontend)
- **State:** JSON file-based (no database) — `.env`, `accounts.json`, `state.json`, `auths/*.json`
- **Deployment:** Docker Compose or bare-metal with Xvfb on Linux

## Common Commands

```bash
# Install dependencies
uv sync
uv run playwright install chromium

# Run the web panel + API server (port 8787)
uv run autoteam api

# CLI commands
uv run autoteam rotate [N]        # Smart rotation targeting N seats
uv run autoteam add               # Auto-register new account
uv run autoteam manual-add        # Manual OAuth import
uv run autoteam status            # View account status
uv run autoteam check             # Check quotas
uv run autoteam fill [N]          # Fill to N members
uv run autoteam cleanup [N]       # Clean excess members
uv run autoteam sync              # Sync active auths to CPA
uv run autoteam pull-cpa          # Reverse-sync from CPA to local
uv run autoteam admin-login       # Admin login to Team
uv run autoteam main-codex-sync   # Sync main account Codex to CPA

# Lint & format
ruff check --fix src/
ruff format src/

# Frontend dev
cd web && npm install && npm run dev    # Dev server on :5173, proxies /api to :8787
cd web && npm run build                 # Builds to src/autoteam/web/dist
```

## Code Quality

- **Ruff** for linting and formatting (line length 120, target py310)
- **Pre-commit hooks** run `ruff check --fix` and `ruff format` automatically on commit
- No test suite exists — there are no automated tests

## Architecture

### Account State Machine

```
active ──quota depleted──> exhausted ──moved out──> standby
   ↑                                                  │
   └──── quota recovered / relogin success ───────────┘
```

### Backend Modules (`src/autoteam/`)

| Module | Role |
|--------|------|
| `manager.py` | CLI entry point (Click), rotation orchestration |
| `api.py` | FastAPI server, auth middleware, background task queue (single concurrent task, returns 202 + task_id) |
| `accounts.py` | Local account pool CRUD (accounts.json) |
| `account_ops.py` | Delete account, fetch actual Team members |
| `chatgpt_api.py` | Playwright browser context, ChatGPT Team internal API calls |
| `codex_auth.py` | Codex OAuth flow, token refresh, quota check, auth file I/O |
| `invite.py` | Auto-registration flow (CloudMail email → chatgpt.com signup → login) |
| `cloudmail.py` | CloudMail temporary email API client |
| `cpa_sync.py` | Bidirectional sync with CLIProxyAPI, deduplication |
| `manual_account.py` | Manual OAuth import (auto localhost callback or manual URL paste) |
| `admin_state.py` | Admin login state persistence (state.json) |
| `setup_wizard.py` | First-time configuration wizard |
| `config.py` | Loads .env into environment |

### Frontend (`web/src/`)

Vue 3 SPA served by FastAPI as static files from `src/autoteam/web/dist`. Dev server proxies `/api` to `:8787`. Components: Dashboard, TeamMembers, PoolPage, SyncPage, OAuthPage, Settings, TaskHistoryPage, LogViewer, SetupPage.

### Key Patterns

- **Single Playwright instance** — browser automation is not parallel; API returns `409 Conflict` if a task is already running
- **Background tasks** — FastAPI wraps long-running operations in threads, returns `202 Accepted` with `task_id` for polling
- **Auth file naming** — `codex-{email}-{plan_type}-{hash}.json` (CLIProxyAPI compatible format)
- **API auth** — Bearer token or `?key=` query param; key from `.env` `API_KEY` (auto-generated if unset)
- **E402 suppression** — `display.py` must be imported before Playwright modules to set up Xvfb on Linux

## Documentation

Detailed docs in `docs/`: `getting-started.md`, `architecture.md`, `api.md`, `configuration.md`, `docker.md`, `troubleshooting.md` (all in Chinese).
