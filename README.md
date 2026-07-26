# JobBot 🤖

A serverless job-alert bot. Every 30 minutes, GitHub Actions polls the public
JSON APIs of the top ATS platforms (Greenhouse, Lever, Ashby, Workable,
SmartRecruiters) for the companies you track, and sends **new** software
engineering postings straight to your Telegram. You control filters and the
company list entirely from Telegram — no code changes, no server, no cost.

No HTML scraping is involved: every ATS here exposes a public job-board API,
so the bot is fast, polite, and doesn't break when a careers page is redesigned.

## Setup (one time, ~10 minutes)

### 1. Create your Telegram bot
1. In Telegram, message [@BotFather](https://t.me/BotFather) → `/newbot` → pick a name and username.
2. Copy the **bot token** it gives you (looks like `123456789:AAF...`).
3. Open a chat with your new bot and send it any message (e.g. "hi") —
   this is needed for the next step.

### 2. Get your chat id
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # paste your bot token into .env
.venv/bin/python -m jobbot --get-chat-id
```
Put the printed chat id into `.env` too.

### 3. Test locally
```bash
.venv/bin/python -m jobbot --dry-run   # fetch + filter, print only, no Telegram
.venv/bin/python -m jobbot             # real run: baselines current jobs, messages you
```
The **first real run** doesn't spam you with thousands of existing postings —
it marks everything currently open as "seen" and confirms it's live. From then
on you only hear about genuinely new postings.

### 4. Deploy to GitHub Actions
1. Create a **private** GitHub repository and push this project to it.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Go to the **Actions** tab, enable workflows, select **JobBot** → **Run workflow**
   to trigger the first run manually. After that it runs every 30 minutes.

The workflow commits `state/state.json` (seen jobs + your filters) back to the
repo after each run — that's how a stateless CI job remembers things.

## Telegram commands

| Command | Effect |
|---|---|
| `/help` | list commands |
| `/filters` | show current filters |
| `/addkeyword new grad` | only titles containing one of your keywords |
| `/delkeyword new grad` | remove a keyword |
| `/addlocation lagos` | only this location (remote jobs always pass) |
| `/dellocation lagos` | remove a location |
| `/remote on` / `/remote off` | only remote postings |
| `/pause` / `/resume` | mute / unmute notifications |
| `/companies` | list tracked company boards |
| `/addcompany greenhouse stripe` | track a new board (validated before saving) |
| `/delcompany greenhouse stripe` | stop tracking a board |

⏱ Commands are read at the start of each scheduled run, so replies can take up
to ~30 minutes. (GitHub's cron can also drift a few minutes — normal.)

Only messages from your `TELEGRAM_CHAT_ID` are honored; anyone else who finds
the bot is ignored.

## Adding companies

The starter list lives in [companies.json](companies.json); edit it or use
`/addcompany` from Telegram. To find a company's slug, look at its careers
page URL:

| ATS | Job board URL pattern | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/stripe` or `job-boards.greenhouse.io/stripe` | `stripe` |
| Lever | `jobs.lever.co/palantir` | `palantir` |
| Ashby | `jobs.ashbyhq.com/openai` | `openai` |
| Workable | `apply.workable.com/kuda` | `kuda` |
| SmartRecruiters | `careers.smartrecruiters.com/ServiceNow` | `servicenow` |

## How matching works

1. A posting's title must look like a SWE role (terms in
   [jobbot/config.py](jobbot/config.py) — `ROLE_TERMS` / `ROLE_EXCLUDE_TERMS`).
2. Your keyword / location / remote filters (from Telegram) are applied on top.
3. Anything not seen before that survives both is sent to you; everything
   fetched is remembered so loosening a filter later doesn't cause a flood.

Seen-job history is pruned after 120 days to keep the state file small.
