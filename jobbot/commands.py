"""Telegram command handling.

Commands arrive via getUpdates and are processed at the start of each
scheduled run, so replies take effect on the next cycle. Only messages from
the configured owner chat are honored.
"""

from datetime import datetime, timedelta, timezone

from .ats import FETCHERS, fetch_all
from .filters import matches
from .state import merged_companies
from .telegram import format_job_line

MAX_RECENT_SHOWN = 30

HELP_TEXT = """<b>JobBot commands</b>
/recent [days] — matching postings from the last N days (default 3)
/filters — show current filters
/addkeyword &lt;word&gt; — title must contain one of your keywords
/delkeyword &lt;word&gt; — remove a keyword
/addlocation &lt;place&gt; — only this location (remote jobs always pass)
/dellocation &lt;place&gt; — remove a location
/remote on|off — only remote postings
/pause — stop notifications (jobs still marked as seen)
/resume — resume notifications
/companies — list tracked companies
/addcompany &lt;ats&gt; &lt;slug&gt; — track a new company board
/delcompany &lt;ats&gt; &lt;slug&gt; — stop tracking a board

ATS values: greenhouse, lever, ashby, workable, smartrecruiters.
Note: commands are processed on the next scheduled run (up to ~30 min)."""


def handle_command(text: str, state: dict, base_companies: dict) -> str:
    parts = text.strip().split()
    if not parts:
        return ""
    cmd = parts[0].lower().split("@")[0]  # strip @botname suffix
    args = parts[1:]
    filters = state["filters"]

    if cmd in ("/start", "/help"):
        return HELP_TEXT

    if cmd == "/recent":
        days = int(args[0]) if args and args[0].isdigit() else 3
        days = max(1, min(days, 30))
        today = datetime.now(timezone.utc).date()
        cutoff = (today - timedelta(days=days)).isoformat()
        jobs, _ = fetch_all(merged_companies(base_companies, state))
        # Jobs not yet in `seen` are brand new, so they count as today.
        first_seen = lambda j: state["seen"].get(j.uid, today.isoformat())
        recent = [j for j in jobs if matches(j, filters) and first_seen(j) >= cutoff]
        if not recent:
            return f"No matching postings from the last {days} day(s)."
        recent.sort(key=first_seen, reverse=True)
        header = f"🕑 <b>{len(recent)} matching posting(s) from the last {days} day(s)</b>"
        if len(recent) > MAX_RECENT_SHOWN:
            header += f" — showing newest {MAX_RECENT_SHOWN}"
        return "\n".join([header] + [format_job_line(j) for j in recent[:MAX_RECENT_SHOWN]])

    if cmd == "/filters":
        return (
            "<b>Current filters</b>\n"
            f"Keywords: {', '.join(filters['keywords']) or '(any SWE title)'}\n"
            f"Locations: {', '.join(filters['locations']) or '(anywhere)'}\n"
            f"Remote only: {'yes' if filters['remote_only'] else 'no'}\n"
            f"Paused: {'yes' if filters['paused'] else 'no'}"
        )

    if cmd == "/addkeyword" and args:
        word = " ".join(args).lower()
        if word not in filters["keywords"]:
            filters["keywords"].append(word)
        return f"Added keyword: {word}\nKeywords: {', '.join(filters['keywords'])}"

    if cmd == "/delkeyword" and args:
        word = " ".join(args).lower()
        if word in filters["keywords"]:
            filters["keywords"].remove(word)
            return f"Removed keyword: {word}"
        return f"Keyword not found: {word}"

    if cmd == "/addlocation" and args:
        place = " ".join(args).lower()
        if place not in filters["locations"]:
            filters["locations"].append(place)
        return f"Added location: {place}\nLocations: {', '.join(filters['locations'])}"

    if cmd == "/dellocation" and args:
        place = " ".join(args).lower()
        if place in filters["locations"]:
            filters["locations"].remove(place)
            return f"Removed location: {place}"
        return f"Location not found: {place}"

    if cmd == "/remote" and args:
        filters["remote_only"] = args[0].lower() in ("on", "yes", "true", "1")
        return f"Remote only: {'on' if filters['remote_only'] else 'off'}"

    if cmd == "/pause":
        filters["paused"] = True
        return "Paused. New jobs will still be marked seen, so you won't get a flood on resume."

    if cmd == "/resume":
        filters["paused"] = False
        return "Resumed. You'll get new postings from the next run onward."

    if cmd == "/companies":
        merged = merged_companies(base_companies, state)
        lines = ["<b>Tracked companies</b>"]
        for ats in sorted(merged):
            if merged[ats]:
                lines.append(f"{ats}: {', '.join(sorted(merged[ats]))}")
        return "\n".join(lines)

    if cmd == "/addcompany" and len(args) == 2:
        ats, slug = args[0].lower(), args[1].lower()
        if ats not in FETCHERS:
            return f"Unknown ATS '{ats}'. Use one of: {', '.join(FETCHERS)}"
        try:
            count = len(FETCHERS[ats](slug))
        except Exception as exc:
            return f"Couldn't fetch {ats}/{slug} — check the slug. ({exc})"
        state["extra_companies"].setdefault(ats, [])
        if slug not in state["extra_companies"][ats]:
            state["extra_companies"][ats].append(slug)
        key = f"{ats}:{slug}"
        if key in state["removed_companies"]:
            state["removed_companies"].remove(key)
        return f"Now tracking {ats}/{slug} ({count} open postings on their board)."

    if cmd == "/delcompany" and len(args) == 2:
        ats, slug = args[0].lower(), args[1].lower()
        key = f"{ats}:{slug}"
        if slug in state["extra_companies"].get(ats, []):
            state["extra_companies"][ats].remove(slug)
        elif key not in state["removed_companies"]:
            state["removed_companies"].append(key)
        return f"Stopped tracking {ats}/{slug}."

    return "Unrecognized command. Send /help for the list."


def process_updates(updates: list[dict], owner_chat_id: str, state: dict,
                    base_companies: dict) -> list[str]:
    """Apply owner commands from pending updates; returns replies to send."""
    replies = []
    for update in updates:
        state["tg_offset"] = max(state["tg_offset"], update["update_id"] + 1)
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        if str(message.get("chat", {}).get("id")) != str(owner_chat_id):
            continue  # ignore strangers
        text = message.get("text", "")
        if text.startswith("/"):
            reply = handle_command(text, state, base_companies)
            if reply:
                replies.append(reply)
    return replies
