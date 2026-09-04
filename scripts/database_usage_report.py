#!/usr/bin/env python3
"""Summarize app database activity from Render logs without connecting to Postgres."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import subprocess


def decode_logs(raw):
    decoder = json.JSONDecoder()
    while raw.strip():
        item, end = decoder.raw_decode(raw.lstrip())
        raw = raw.lstrip()[end:]
        yield from item if isinstance(item, list) else [item]


def summarize(logs):
    totals = defaultdict(Counter)
    minutes = defaultdict(set)
    windows = []
    revisions = set()
    for log in logs:
        message = log.get("message", "")
        marker = "Database usage {"
        if marker not in message:
            continue
        payload = json.loads(message[message.index(marker) + len("Database usage ") :])
        windows.append((payload["window_start"], payload["window_end"]))
        revisions.add(payload.get("revision", "unknown"))
        for source, counts in payload["sources"].items():
            minutes[source].update(counts.get("db_minutes", []))
            totals[source].update(
                {key: value for key, value in counts.items() if key != "db_minutes"}
            )
    return totals, minutes, windows, revisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources",
        required=True,
        help="Comma-separated Render API and worker service IDs",
    )
    parser.add_argument("--hours", type=float, default=24)
    args = parser.parse_args()
    if args.hours <= 0:
        parser.error("--hours must be positive")
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    result = subprocess.run(
        [
            "render",
            "logs",
            "--resources",
            args.resources,
            "--start",
            start.isoformat(),
            "--end",
            end.isoformat(),
            "--text",
            "Database usage {",
            "--limit",
            "1000",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    logs = list(decode_logs(result.stdout))
    totals, minutes, windows, revisions = summarize(logs)
    print(f"Requested UTC window: {start.isoformat()} -> {end.isoformat()}")
    if not windows:
        print(
            "No activity summaries found. Confirm the instrumented API and worker are deployed; idle processes emit no empty summaries."
        )
        return
    print(f"Summary windows: {len(windows)}; revisions: {', '.join(sorted(revisions))}")
    print(
        f"Reported coverage: {min(w[0] for w in windows)} -> {max(w[1] for w in windows)}"
    )
    print(
        "Source | Connections | Statements | Commits | Rollbacks | Errors | Cache hits / fills / discarded | DB-active minutes"
    )
    for source, counts in sorted(
        totals.items(), key=lambda row: (-row[1]["connections"], row[0])
    ):
        print(
            f"{source} | {counts['connections']} | {counts['statements']} | {counts['commits']} | {counts['rollbacks']} | {counts['errors']} | {counts['game_cache_hits']} / {counts['game_cache_fills']} / {counts['game_cache_discarded_fills']} | {len(minutes[source])}"
        )
    activity = sorted(set().union(*minutes.values()))
    print(
        f"Distinct minutes with observed DB activity across both services: {len(activity)}"
    )
    if activity:
        print(f"First / last observed activity: {activity[0]} / {activity[-1]}")
    hourly = defaultdict(lambda: defaultdict(set))
    for source, observed in minutes.items():
        for minute in observed:
            hourly[minute[:13]][source].add(minute)
    print("Observed DB activity by UTC hour (minutes per source, not awake time):")
    for hour, sources in sorted(hourly.items()):
        details = "; ".join(
            f"{source}={len(observed)}" for source, observed in sorted(sources.items())
        )
        print(f"{hour}:00Z | {details}")
    if len(logs) >= 1000:
        print(
            "WARNING: log result limit reached; rerun with a shorter window before drawing conclusions."
        )
    print(
        "Activity minutes are not Neon awake hours or CU-hours. Compare Neon usage snapshots for those; logs only attribute application activity. Windows crossing the requested boundary are included whole. The current partial window and abrupt shutdowns can be missing."
    )


if __name__ == "__main__":
    main()
