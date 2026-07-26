"""Entry point: process pending Telegram commands, fetch boards, notify.

Usage:
  python -m jobbot                 # normal run (needs TELEGRAM_* env vars)
  python -m jobbot --dry-run       # fetch + filter, print to stdout, no state changes
  python -m jobbot --get-chat-id   # discover your chat id after messaging the bot
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from . import commands, filters, telegram
from .ats import fetch_all
from .config import load_companies, load_dotenv
from .state import load_state, merged_companies, prune_seen, save_state


def print_chat_ids(token: str) -> None:
    updates = telegram.get_updates(token, offset=0)
    chats = {}
    for update in updates:
        chat = (update.get("message") or {}).get("chat")
        if chat:
            name = chat.get("username") or chat.get("first_name") or "?"
            chats[chat["id"]] = name
    if not chats:
        print("No messages found. Send your bot any message on Telegram, then rerun.")
        return
    for chat_id, name in chats.items():
        print(f"chat_id: {chat_id}  ({name})")


def main() -> int:
    parser = argparse.ArgumentParser(prog="jobbot")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and print matches without Telegram or state changes")
    parser.add_argument("--get-chat-id", action="store_true",
                        help="print chat ids of people who messaged the bot")
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if args.get_chat_id:
        if not token:
            print("Set TELEGRAM_BOT_TOKEN first.", file=sys.stderr)
            return 1
        print_chat_ids(token)
        return 0

    state = load_state()
    base_companies = load_companies()

    if not args.dry_run:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.", file=sys.stderr)
            return 1
        updates = telegram.get_updates(token, state["tg_offset"])
        for target, reply in commands.process_updates(updates, chat_id, state, base_companies):
            telegram.send_long_message(token, target, reply.split("\n"))

    companies = merged_companies(base_companies, state)
    jobs, errors = fetch_all(companies)
    for err in errors:
        print(f"warning: {err}", file=sys.stderr)
    print(f"Fetched {len(jobs)} postings from "
          f"{sum(len(v) for v in companies.values())} company boards.")

    new_matches = [
        j for j in jobs
        if j.uid not in state["seen"] and filters.matches(j, state["filters"])
    ]

    if args.dry_run:
        print(f"{len(new_matches)} new matching postings "
              f"(state untouched — every run will look 'new' until a real run):")
        for job in new_matches:
            print(f"  [{job.ats}/{job.company}] {job.title} — {job.location}\n"
                  f"    {job.url}")
        return 0

    today = datetime.now(timezone.utc).date().isoformat()
    for job in jobs:
        state["seen"].setdefault(job.uid, today)

    if not state["initialized"]:
        state["initialized"] = True
        telegram.send_message(
            token, chat_id,
            "🤖 <b>JobBot is live!</b>\n"
            f"Tracking {sum(len(v) for v in companies.values())} company boards "
            f"({len(jobs)} current postings baselined as seen).\n"
            "You'll be notified about new postings from now on. Send /help for commands.",
        )
    elif new_matches and not state["filters"]["paused"]:
        header = f"🆕 <b>{len(new_matches)} new job posting{'s' if len(new_matches) != 1 else ''}</b>"
        lines = [header] + [telegram.format_job_line(j) for j in new_matches]
        recipients = [chat_id] + [s for s in state.get("subscribers", []) if s != str(chat_id)]
        for recipient in recipients:
            try:
                telegram.send_long_message(token, recipient, lines)
            except Exception as exc:
                print(f"warning: couldn't message {recipient}: {exc}", file=sys.stderr)
        print(f"Sent {len(new_matches)} new postings to {len(recipients)} chat(s).")
    else:
        print("No new matching postings.")

    prune_seen(state)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
