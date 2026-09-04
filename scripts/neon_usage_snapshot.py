#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr.strip() or p.stdout.strip(), file=sys.stderr)
        sys.exit(p.returncode)
    return p.stdout


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def hours_between(start_iso: str, end_iso: str) -> float:
    return (parse_ts(end_iso) - parse_ts(start_iso)).total_seconds() / 3600


def main():
    parser = argparse.ArgumentParser(
        description="Capture and compare Neon compute usage snapshots"
    )
    parser.add_argument("--project-id", required=True, help="Neon project id")
    parser.add_argument("--org-id", help="Neon org id (optional if context is set)")
    parser.add_argument(
        "--out-dir", default=".cache/neon-usage", help="Snapshot directory"
    )
    args = parser.parse_args()

    cmd = ["neon", "projects", "get", args.project_id, "-o", "json"]
    if args.org_id:
        cmd.extend(["--org-id", args.org_id])

    raw = run(cmd)
    data = json.loads(raw)

    ts = now_utc()
    snapshot = {
        "captured_at": ts.isoformat(),
        "project_id": data["id"],
        "project_name": data.get("name"),
        "org_id": data.get("org_id"),
        "consumption_period_start": data.get("consumption_period_start"),
        "consumption_period_end": data.get("consumption_period_end"),
        "cpu_used_sec": data.get("cpu_used_sec"),
        "active_time_sec": data.get("active_time_seconds"),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"neon-usage-{ts.strftime('%Y%m%dT%H%M%SZ')}.json"
    fname.write_text(json.dumps(snapshot, indent=2) + "\n")

    previous = [
        json.loads(path.read_text())
        for path in sorted(out_dir.glob("neon-usage-*.json"))
        if path != fname
    ]
    previous = [
        item
        for item in previous
        if item.get("project_id") == snapshot["project_id"]
        and item.get("consumption_period_start") == snapshot["consumption_period_start"]
    ]

    print(f"Saved snapshot: {fname}")
    print(f"Project: {snapshot['project_name']} ({snapshot['project_id']})")
    print(
        f"Cycle: {snapshot['consumption_period_start']} -> {snapshot['consumption_period_end']}"
    )
    print(
        f"Totals now: cpu_used_sec={snapshot['cpu_used_sec']}, active_time_sec={snapshot['active_time_sec']}"
    )

    if not previous:
        print("\nNeed one more snapshot to compute interval burn rate.")
        return

    prev = previous[-1]
    cur = snapshot

    t0 = parse_ts(prev["captured_at"])
    t1 = parse_ts(cur["captured_at"])
    delta_hours = (t1 - t0).total_seconds() / 3600

    if any(
        not isinstance(item.get(key), (int, float))
        for item in (prev, cur)
        for key in ("cpu_used_sec", "active_time_sec")
    ):
        print("\nCannot compute delta: Neon usage counters are unavailable (not zero).")
        return

    d_cpu_sec = cur["cpu_used_sec"] - prev["cpu_used_sec"]
    d_active_sec = cur["active_time_sec"] - prev["active_time_sec"]

    if delta_hours <= 0 or d_cpu_sec < 0 or d_active_sec < 0:
        print("\nCannot compute delta (counter reset or invalid timestamp ordering).")
        return

    d_cpu_hours = d_cpu_sec / 3600
    d_active_hours = d_active_sec / 3600
    cu_per_wall_hour = d_cpu_hours / delta_hours
    active_pct = (d_active_hours / delta_hours) * 100
    cu_while_active = (d_cpu_sec / d_active_sec) if d_active_sec > 0 else 0.0

    print("\nInterval comparison (latest two snapshots):")
    print(f"Window: {prev['captured_at']} -> {cur['captured_at']} ({delta_hours:.2f}h)")
    print(f"Delta cpu: {d_cpu_sec} sec ({d_cpu_hours:.3f} CU-hours)")
    print(f"Delta active: {d_active_sec} sec ({d_active_hours:.3f} active hours)")
    print(f"Avg CU across wall time: {cu_per_wall_hour:.3f} CU/hour")
    print(f"Active ratio: {active_pct:.1f}% of wall time")
    print(f"Avg CU while active: {cu_while_active:.3f} CU")
    projected_interval_month = cu_per_wall_hour * 24 * 31
    print(
        f"Projected 31-day usage at this interval rate: {projected_interval_month:.1f} CU-hours"
    )

    # Also show cycle-to-date pace to avoid overreacting to short bursty intervals.
    cycle_start = cur.get("consumption_period_start")
    if cycle_start:
        elapsed_cycle_hours = hours_between(cycle_start, cur["captured_at"])
        if elapsed_cycle_hours > 0:
            cycle_cpu_hours = cur["cpu_used_sec"] / 3600
            cycle_cu_per_hour = cycle_cpu_hours / elapsed_cycle_hours
            projected_cycle_month = cycle_cu_per_hour * 24 * 31
            print("\nCycle-to-date pace:")
            print(f"Elapsed in cycle: {elapsed_cycle_hours:.1f}h")
            print(f"CPU used in cycle: {cycle_cpu_hours:.3f} CU-hours")
            print(f"Avg CU across wall time (cycle): {cycle_cu_per_hour:.3f} CU/hour")
            print(
                f"Projected 31-day usage from cycle pace: {projected_cycle_month:.1f} CU-hours"
            )

    if delta_hours < 6:
        print(
            "\nWarning: interval < 6h. Projection may be noisy due to bursty traffic."
        )


if __name__ == "__main__":
    main()
