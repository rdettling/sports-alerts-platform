"""Report production database usage from Neon control-plane data and Render logs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NEON_PROJECT_ID = "solitary-resonance-98873129"
RENDER_PROJECT_NAME = "sports-alerts-platform"
RENDER_ENVIRONMENT_NAME = "Production"
RENDER_SERVICES = {
    "sports-alerts-platform-api": "web_service",
    "sports-alerts-platform-worker": "background_worker",
}
REPORT_TIMEZONE = ZoneInfo("America/Los_Angeles")
RENDER_LOG_LIMIT = 1000
RENDER_RETENTION_DAYS = 7
MIN_RENDER_SLICE = timedelta(minutes=1)
COVERAGE_GRACE = timedelta(minutes=10)
DATABASE_USAGE_MARKER = "Database usage "


class CommandError(RuntimeError):
    pass


CommandRunner = Callable[[list[str], int], str]


@dataclass
class LifecycleSummary:
    intervals: list[tuple[datetime, datetime]] = field(default_factory=list)
    starts: list[datetime] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def active_hours(self) -> float:
        return sum((end - start).total_seconds() for start, end in self.intervals) / 3600


@dataclass
class NeonReport:
    status: str = "UNAVAILABLE"
    project: dict = field(default_factory=dict)
    lifecycle: LifecycleSummary = field(default_factory=LifecycleSummary)
    lifecycle_available: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class RenderReport:
    status: str = "UNAVAILABLE"
    logs: list[dict] = field(default_factory=list)
    totals: dict[str, Counter] = field(default_factory=dict)
    minutes: dict[str, set[str]] = field(default_factory=dict)
    windows: list[tuple[str, str]] = field(default_factory=list)
    revisions: dict[str, tuple[str, str, int]] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


def run_command(command: list[str], attempts: int = 1) -> str:
    error = "command failed"
    for _ in range(attempts):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout
        error = result.stderr.strip() or result.stdout.strip() or error
    raise CommandError(error)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_json_stream(raw: str) -> Iterable[dict]:
    decoder = json.JSONDecoder()
    remaining = raw
    while remaining.strip():
        stripped = remaining.lstrip()
        item, end = decoder.raw_decode(stripped)
        remaining = stripped[end:]
        values = item if isinstance(item, list) else [item]
        for value in values:
            if isinstance(value, dict):
                yield value


def preflight_cli(name: str, command: list[str], login_command: str, runner: CommandRunner) -> str | None:
    if shutil.which(name) is None:
        return f"{name} CLI is not installed."
    try:
        runner(command, 1)
    except CommandError as exc:
        return f"{name} authentication failed ({exc}). Run `{login_command}`."
    return None


def discover_render_resources(raw: str) -> list[str]:
    services = json.loads(raw)
    matches: dict[str, list[str]] = {name: [] for name in RENDER_SERVICES}
    for item in services:
        service = item.get("service") or {}
        project = item.get("project") or {}
        environment = item.get("environment") or {}
        name = service.get("name")
        if (
            project.get("name") == RENDER_PROJECT_NAME
            and environment.get("name") == RENDER_ENVIRONMENT_NAME
            and name in RENDER_SERVICES
            and service.get("type") == RENDER_SERVICES[name]
            and service.get("id")
        ):
            matches[name].append(service["id"])

    invalid = [name for name, ids in matches.items() if len(ids) != 1]
    if invalid:
        details = ", ".join(f"{name}={len(matches[name])} matches" for name in invalid)
        raise ValueError(f"Render production service discovery was ambiguous or incomplete: {details}")
    return [matches[name][0] for name in RENDER_SERVICES]


def fetch_neon_operations(
    start: datetime,
    runner: CommandRunner,
) -> tuple[list[dict], list[str]]:
    operations: dict[str, dict] = {}
    cursor: str | None = None
    fetched_past_start = False
    flags: list[str] = []

    while True:
        command = [
            "neon",
            "api",
            f"/projects/{NEON_PROJECT_ID}/operations",
            "-Q",
            "limit=1000",
            "-o",
            "json",
        ]
        if cursor:
            command.extend(["-Q", f"cursor={cursor}"])
        data = json.loads(runner(command, 2))
        page = data.get("operations") or []
        for operation in page:
            operation_id = operation.get("id")
            if operation_id:
                operations[operation_id] = operation

        lifecycle_times = [
            parse_timestamp(item["created_at"])
            for item in page
            if item.get("action") in {"start_compute", "suspend_compute"}
            and item.get("created_at")
        ]
        if lifecycle_times and min(lifecycle_times) < start:
            fetched_past_start = True
            break

        next_cursor = (data.get("pagination") or {}).get("cursor")
        if not next_cursor or not page:
            break
        if next_cursor == cursor:
            flags.append("Neon operation pagination returned a repeated cursor.")
            break
        cursor = next_cursor

    if not fetched_past_start:
        flags.append("Neon operation history did not include a lifecycle event before the requested window.")
    return list(operations.values()), flags


def build_lifecycle_summary(
    operations: list[dict], start: datetime, end: datetime
) -> LifecycleSummary:
    summary = LifecycleSummary()
    grouped: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for operation in operations:
        action = operation.get("action")
        created_at = operation.get("created_at")
        if action not in {"start_compute", "suspend_compute"} or not created_at:
            continue
        if operation.get("status") != "finished":
            if start <= parse_timestamp(created_at) <= end:
                summary.flags.append(
                    f"Unfinished Neon lifecycle operation {operation.get('id', 'unknown')} was ignored."
                )
            continue
        grouped[operation.get("endpoint_id") or "unknown"].append(
            (parse_timestamp(created_at), action)
        )

    for endpoint, events in sorted(grouped.items()):
        events.sort()
        predecessor = next(
            ((when, action) for when, action in reversed(events) if when < start),
            None,
        )
        active = predecessor is not None and predecessor[1] == "start_compute"
        active_since = start if active else None
        relevant = [(when, action) for when, action in events if start <= when < end]

        if predecessor is None and relevant and relevant[0][1] == "suspend_compute":
            active = True
            active_since = start
            summary.flags.append(
                f"Endpoint {endpoint} first appears as a suspension; awake time before it is inferred."
            )

        for when, action in relevant:
            if action == "start_compute":
                summary.starts.append(when)
                if active:
                    summary.flags.append(f"Endpoint {endpoint} has consecutive start operations.")
                    continue
                active = True
                active_since = when
                continue

            if not active or active_since is None:
                summary.flags.append(f"Endpoint {endpoint} has a suspension without a matching start.")
                continue
            summary.intervals.append((active_since, when))
            active = False
            active_since = None

        if active and active_since is not None:
            summary.intervals.append((active_since, end))

    summary.intervals.sort()
    summary.starts.sort()
    summary.flags = list(dict.fromkeys(summary.flags))
    return summary


def collect_neon(start: datetime, end: datetime, runner: CommandRunner) -> NeonReport:
    report = NeonReport()
    issue = preflight_cli("neon", ["neon", "me"], "neon auth", runner)
    if issue:
        report.flags.append(issue)
        return report

    counters_available = False
    try:
        report.project = json.loads(
            runner(["neon", "projects", "get", NEON_PROJECT_ID, "-o", "json"], 2)
        )
        counters_available = True
    except (CommandError, json.JSONDecodeError) as exc:
        report.flags.append(f"Neon project counters are unavailable: {exc}")

    if counters_available:
        missing_counters = [
            key
            for key in (
                "cpu_used_sec",
                "active_time_seconds",
                "consumption_period_start",
                "consumption_period_end",
            )
            if report.project.get(key) is None
        ]
        if missing_counters:
            report.flags.append(
                "Neon project counters are unavailable: " + ", ".join(missing_counters)
            )

    lifecycle_available = False
    try:
        operations, flags = fetch_neon_operations(start, runner)
        report.flags.extend(flags)
        report.lifecycle = build_lifecycle_summary(operations, start, end)
        report.lifecycle_available = True
        report.flags.extend(report.lifecycle.flags)
        lifecycle_available = True
    except (CommandError, json.JSONDecodeError, KeyError, ValueError) as exc:
        report.flags.append(f"Neon lifecycle history is unavailable: {exc}")

    if not counters_available and not lifecycle_available:
        report.status = "UNAVAILABLE"
    else:
        report.status = "PARTIAL" if report.flags else "COMPLETE"
    return report


def fetch_render_logs(
    resources: list[str],
    start: datetime,
    end: datetime,
    runner: CommandRunner,
) -> tuple[list[dict], list[str]]:
    logs: dict[str, dict] = {}
    flags: list[str] = []

    def fetch_slice(slice_start: datetime, slice_end: datetime) -> None:
        command = [
            "render",
            "logs",
            "--resources",
            ",".join(resources),
            "--start",
            format_timestamp(slice_start),
            "--end",
            format_timestamp(slice_end),
            "--text",
            "Database usage {",
            "--limit",
            str(RENDER_LOG_LIMIT),
            "--output",
            "json",
        ]
        try:
            page = list(decode_json_stream(runner(command, 2)))
        except (CommandError, json.JSONDecodeError) as exc:
            flags.append(
                f"Render log query failed for {format_timestamp(slice_start)} -> "
                f"{format_timestamp(slice_end)}: {exc}"
            )
            return

        if len(page) >= RENDER_LOG_LIMIT:
            if slice_end - slice_start <= MIN_RENDER_SLICE:
                flags.append(
                    f"Render log slice remained capped at {RENDER_LOG_LIMIT} records: "
                    f"{format_timestamp(slice_start)} -> {format_timestamp(slice_end)}."
                )
                for log in page:
                    if log.get("id"):
                        logs[log["id"]] = log
                return
            midpoint = slice_start + (slice_end - slice_start) / 2
            fetch_slice(slice_start, midpoint)
            fetch_slice(midpoint, slice_end)
            return

        for log in page:
            log_id = log.get("id")
            if log_id:
                logs[log_id] = log

    fetch_slice(start, end)
    return list(logs.values()), flags


def summarize_render_logs(logs: list[dict]) -> tuple[
    dict[str, Counter],
    dict[str, set[str]],
    list[tuple[str, str]],
    dict[str, tuple[str, str, int]],
    list[str],
]:
    totals: dict[str, Counter] = defaultdict(Counter)
    minutes: dict[str, set[str]] = defaultdict(set)
    windows: list[tuple[str, str]] = []
    revision_times: dict[str, list[str]] = defaultdict(list)
    flags: list[str] = []

    for log in logs:
        message = log.get("message", "")
        if DATABASE_USAGE_MARKER not in message:
            continue
        try:
            payload = json.loads(message[message.index(DATABASE_USAGE_MARKER) + len(DATABASE_USAGE_MARKER) :])
            windows.append((payload["window_start"], payload["window_end"]))
            revision = payload.get("revision", "unknown")
            revision_times[revision].append(log.get("timestamp") or payload["window_end"])
            for source, counts in payload["sources"].items():
                minutes[source].update(counts.get("db_minutes", []))
                totals[source].update(
                    {key: value for key, value in counts.items() if key != "db_minutes"}
                )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            flags.append(f"Render log {log.get('id', 'unknown')} contained an invalid usage summary.")

    revisions = {
        revision: (min(times), max(times), len(times))
        for revision, times in revision_times.items()
    }
    return dict(totals), dict(minutes), windows, revisions, flags


def collect_render(
    start: datetime, end: datetime, days: int, runner: CommandRunner
) -> RenderReport:
    report = RenderReport()
    issue = preflight_cli("render", ["render", "whoami"], "render login", runner)
    if issue:
        report.flags.append(issue)
        return report

    try:
        resources = discover_render_resources(runner(["render", "services", "--output", "json"], 2))
    except (CommandError, json.JSONDecodeError, ValueError) as exc:
        report.flags.append(str(exc))
        return report

    report.logs, query_flags = fetch_render_logs(resources, start, end, runner)
    report.flags.extend(query_flags)
    (
        report.totals,
        report.minutes,
        report.windows,
        report.revisions,
        summary_flags,
    ) = summarize_render_logs(report.logs)
    report.flags.extend(summary_flags)
    if days > RENDER_RETENTION_DAYS:
        report.flags.append(
            f"The requested range exceeds Render's {RENDER_RETENTION_DAYS}-day log retention; "
            "earlier attribution may be unavailable."
        )
    if not report.windows:
        report.flags.append(
            "No Render database-usage summaries were observed; idle time and missing logs cannot be distinguished."
        )

    report.status = "PARTIAL" if report.flags else "COMPLETE"
    return report


def reconcile_coverage(
    neon: NeonReport,
    render: RenderReport,
    start: datetime,
    end: datetime,
) -> None:
    if neon.status == "UNAVAILABLE" or render.status == "UNAVAILABLE" or not render.windows:
        return

    first_render = min(parse_timestamp(window[0]) for window in render.windows)
    last_render = max(parse_timestamp(window[1]) for window in render.windows)
    missing_start = overlap_seconds(
        neon.lifecycle.intervals,
        start,
        min(first_render, end),
    )
    missing_end = overlap_seconds(
        neon.lifecycle.intervals,
        max(last_render, start),
        end,
    )
    if first_render - start > COVERAGE_GRACE and missing_start > COVERAGE_GRACE.total_seconds():
        render.flags.append(
            f"Neon shows {missing_start / 3600:.2f} active hours before the first Render usage "
            "summary; attribution for that leading period is unavailable."
        )
    if end - last_render > COVERAGE_GRACE and missing_end > COVERAGE_GRACE.total_seconds():
        render.flags.append(
            f"Neon shows {missing_end / 3600:.2f} active hours after the last Render usage "
            "summary; attribution for that trailing period is unavailable."
        )
    if render.flags:
        render.status = "PARTIAL"


def counter_number(data: dict, key: str) -> float | None:
    value = data.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def neon_metrics(project: dict, captured_at: datetime) -> dict[str, float | datetime | None]:
    cpu_seconds = counter_number(project, "cpu_used_sec")
    active_seconds = counter_number(project, "active_time_seconds")
    cycle_start_raw = project.get("consumption_period_start")
    cycle_end_raw = project.get("consumption_period_end")
    cycle_start = parse_timestamp(cycle_start_raw) if cycle_start_raw else None
    cycle_end = parse_timestamp(cycle_end_raw) if cycle_end_raw else None
    average_cu = (
        cpu_seconds / active_seconds
        if cpu_seconds is not None and active_seconds is not None and active_seconds > 0
        else None
    )
    projection = None
    if cpu_seconds is not None and cycle_start and cycle_end and captured_at > cycle_start:
        elapsed = (captured_at - cycle_start).total_seconds()
        projection = cpu_seconds / 3600 * (cycle_end - cycle_start).total_seconds() / elapsed
    return {
        "cpu_hours": cpu_seconds / 3600 if cpu_seconds is not None else None,
        "active_hours": active_seconds / 3600 if active_seconds is not None else None,
        "average_cu": average_cu,
        "projection": projection,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, REPORT_TIMEZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, REPORT_TIMEZONE).astimezone(timezone.utc)
    return start, end


def iter_local_days(start: datetime, end: datetime) -> Iterable[date]:
    current = start.astimezone(REPORT_TIMEZONE).date()
    while local_day_bounds(current)[0] < end:
        yield current
        current += timedelta(days=1)


def overlap_seconds(
    intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime
) -> float:
    return sum(
        max(0.0, (min(interval_end, end) - max(interval_start, start)).total_seconds())
        for interval_start, interval_end in intervals
        if interval_end > start and interval_start < end
    )


def render_activity_by_day(minutes: dict[str, set[str]]) -> Counter:
    result: Counter = Counter()
    observed = set().union(*minutes.values()) if minutes else set()
    for minute in observed:
        day = parse_timestamp(minute).astimezone(REPORT_TIMEZONE).date()
        result[day] += 1
    return result


def git_subject(revision: str, runner: CommandRunner) -> str | None:
    if revision == "unknown":
        return None
    try:
        return runner(["git", "show", "-s", "--format=%s", revision], 1).strip() or None
    except CommandError:
        return None


def format_optional(value: float | None, suffix: str = "", digits: int = 2) -> str:
    return "unavailable" if value is None else f"{value:.{digits}f}{suffix}"


def build_report(
    captured_at: datetime,
    start: datetime,
    days: int,
    neon: NeonReport,
    render: RenderReport,
    runner: CommandRunner,
) -> str:
    lines = [
        "Production database usage report",
        f"Captured: {format_timestamp(captured_at)}",
        f"Requested: {format_timestamp(start)} -> {format_timestamp(captured_at)} ({days} days)",
        f"Sources: Neon={neon.status}; Render={render.status}",
        "",
        "Coverage",
    ]
    if not neon.lifecycle_available:
        lines.append("Neon lifecycle: unavailable")
    else:
        lines.append(
            f"Neon lifecycle: {len(neon.lifecycle.intervals)} active intervals; "
            f"{len(neon.lifecycle.starts)} starts in requested window"
        )
    if render.windows:
        lines.append(
            f"Render observed summaries: {min(item[0] for item in render.windows)} -> "
            f"{max(item[1] for item in render.windows)} ({len(render.logs)} records)"
        )
    else:
        lines.append("Render observed summaries: none")

    metrics = neon_metrics(neon.project, captured_at) if neon.project else {}
    if neon.project:
        cycle_start = metrics.get("cycle_start")
        cycle_end = metrics.get("cycle_end")
        cycle_start_text = (
            format_timestamp(cycle_start) if isinstance(cycle_start, datetime) else "unavailable"
        )
        cycle_end_text = (
            format_timestamp(cycle_end) if isinstance(cycle_end, datetime) else "unavailable"
        )
        lines.extend(
            [
                "",
                "Neon counters (exact as reported by Neon; counters may lag)",
                f"Billing cycle: {cycle_start_text} -> {cycle_end_text}",
                f"Cycle CU-hours: {format_optional(metrics.get('cpu_hours'), digits=3)}",
                f"Cycle active hours: {format_optional(metrics.get('active_hours'), digits=3)}",
                f"Average CU while active: {format_optional(metrics.get('average_cu'), digits=3)}",
                f"Cycle-pace projection: {format_optional(metrics.get('projection'), ' CU-hours', 1)}",
            ]
        )

    average_cu = metrics.get("average_cu") if metrics else None
    window_estimate = (
        neon.lifecycle.active_hours * average_cu
        if isinstance(average_cu, float) and neon.lifecycle_available
        else None
    )
    lines.extend(
        [
            "",
            "Requested window",
            "Lifecycle-derived compute-active hours: "
            + format_optional(
                neon.lifecycle.active_hours if neon.lifecycle_available else None,
                digits=3,
            ),
            f"Estimated CU-hours: {format_optional(window_estimate, digits=3)}",
            "",
            "Pacific daily activity",
            "Date | Coverage | Awake hours | Starts | Est. CU-hours | Render-active minutes",
        ]
    )
    render_daily = render_activity_by_day(render.minutes)
    for day in iter_local_days(start, captured_at):
        day_start, day_end = local_day_bounds(day)
        clipped_start = max(start, day_start)
        clipped_end = min(captured_at, day_end)
        partial = clipped_start > day_start or clipped_end < day_end
        awake = (
            overlap_seconds(neon.lifecycle.intervals, clipped_start, clipped_end) / 3600
            if neon.lifecycle_available
            else None
        )
        starts = (
            sum(clipped_start <= item < clipped_end for item in neon.lifecycle.starts)
            if neon.lifecycle_available
            else None
        )
        estimated = (
            awake * average_cu
            if awake is not None and isinstance(average_cu, float)
            else None
        )
        lines.append(
            f"{day.isoformat()} | {'partial' if partial else 'full'} | "
            f"{format_optional(awake, digits=3)} | "
            f"{starts if starts is not None else 'unavailable'} | "
            f"{format_optional(estimated, digits=3)} | "
            f"{render_daily.get(day, 0) if render.windows else 'unavailable'}"
        )

    if render.totals:
        api_sources = [source for source in render.totals if source.startswith("api:")]
        worker_sources = [source for source in render.totals if source.startswith("worker:")]
        observed_minutes = set().union(*render.minutes.values()) if render.minutes else set()
        attribution_totals = (
            f"Totals: API connections={sum(render.totals[source]['connections'] for source in api_sources)}; "
            f"worker connections={sum(render.totals[source]['connections'] for source in worker_sources)}; "
            f"distinct active minutes={len(observed_minutes)}"
        )
        lines.extend(
            [
                "",
                "Render-observed attribution (top sources by connections)",
                attribution_totals,
                "Source | Connections | Statements | Errors | Active minutes",
            ]
        )
        ranked = sorted(
            render.totals.items(),
            key=lambda item: (-item[1]["connections"], item[0]),
        )
        for source, counts in ranked[:10]:
            lines.append(
                f"{source} | {counts['connections']} | {counts['statements']} | "
                f"{counts['errors']} | {len(render.minutes.get(source, set()))}"
            )
        remaining = ranked[10:]
        if remaining:
            lines.append(
                f"Other {len(remaining)} sources | "
                f"{sum(item[1]['connections'] for item in remaining)} | "
                f"{sum(item[1]['statements'] for item in remaining)} | "
                f"{sum(item[1]['errors'] for item in remaining)} | n/a"
            )
        cache_hits = sum(counts["game_cache_hits"] for counts in render.totals.values())
        cache_fills = sum(counts["game_cache_fills"] for counts in render.totals.values())
        discarded = sum(
            counts["game_cache_discarded_fills"] for counts in render.totals.values()
        )
        lines.append(f"Game cache: hits={cache_hits}; fills={cache_fills}; discarded_fills={discarded}")
        error_sources = [
            f"{source}={counts['errors']}"
            for source, counts in sorted(render.totals.items())
            if counts["errors"]
        ]
        lines.append(
            "Database errors: " + (", ".join(error_sources) if error_sources else "none")
        )

    if render.revisions:
        lines.extend(["", "Deployment revisions"])
        for revision, (first, last, count) in sorted(
            render.revisions.items(), key=lambda item: item[1][0]
        ):
            subject = git_subject(revision, runner)
            description = f" — {subject}" if subject else ""
            lines.append(
                f"{revision[:7]} | {first} -> {last} | {count} summaries{description}"
            )

    flags = list(dict.fromkeys(neon.flags + render.flags))
    lines.extend(["", "Flags"])
    lines.extend(f"- {flag}" for flag in flags)
    if not flags:
        lines.append("- None")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Positive number of days to review (default: 7)")
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    captured_at = datetime.now(timezone.utc)
    start = captured_at - timedelta(days=args.days)
    neon = collect_neon(start, captured_at, run_command)
    render = collect_render(start, captured_at, args.days, run_command)
    reconcile_coverage(neon, render, start, captured_at)
    print(build_report(captured_at, start, args.days, neon, render, run_command))
    return 0 if neon.status == "COMPLETE" and render.status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
