import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "production_usage_report.py"


def load_report():
    spec = importlib.util.spec_from_file_location("production_usage_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def render_service(name, service_type, *, project="sports-alerts-platform", environment="Production"):
    return {
        "service": {"id": f"srv-{name}", "name": name, "type": service_type},
        "project": {"name": project},
        "environment": {"name": environment},
    }


def operation(identifier, endpoint, action, created_at, status="finished"):
    return {
        "id": identifier,
        "endpoint_id": endpoint,
        "action": action,
        "status": status,
        "created_at": created_at,
    }


def usage_log(identifier, timestamp, payload):
    return {
        "id": identifier,
        "timestamp": timestamp,
        "message": "2026-09-04 INFO Database usage " + json.dumps(payload),
    }


def test_decode_and_summarize_render_logs():
    report = load_report()
    payload = {
        "revision": "abc123",
        "window_start": "2026-09-04T00:00:00Z",
        "window_end": "2026-09-04T00:05:00Z",
        "sources": {
            "api:GET /games": {
                "connections": 1,
                "game_cache_hits": 2,
                "db_minutes": ["2026-09-04T00:01Z"],
            }
        },
    }
    log = usage_log("one", "2026-09-04T00:05:00Z", payload)
    decoded = list(report.decode_json_stream(json.dumps(log) + json.dumps([log])))
    assert decoded == [log, log]

    totals, minutes, windows, revisions, flags = report.summarize_render_logs(decoded)
    assert totals["api:GET /games"]["connections"] == 2
    assert totals["api:GET /games"]["game_cache_hits"] == 4
    assert minutes["api:GET /games"] == {"2026-09-04T00:01Z"}
    assert len(windows) == 2
    assert revisions["abc123"][2] == 2
    assert flags == []


def test_render_service_discovery_requires_one_exact_match():
    report = load_report()
    services = [
        render_service("sports-alerts-platform-api", "web_service"),
        render_service("sports-alerts-platform-worker", "background_worker"),
        render_service("sports-alerts-platform-frontend", "static_site"),
        render_service("sports-alerts-platform-api", "web_service", project="another"),
    ]
    assert report.discover_render_resources(json.dumps(services)) == [
        "srv-sports-alerts-platform-api",
        "srv-sports-alerts-platform-worker",
    ]

    with pytest.raises(ValueError, match="worker=0 matches"):
        report.discover_render_resources(json.dumps(services[:1]))

    with pytest.raises(ValueError, match="api=2 matches"):
        report.discover_render_resources(json.dumps([services[0], services[0], services[1]]))


def test_render_log_fetch_splits_capped_ranges_and_deduplicates():
    report = load_report()
    start = report.parse_timestamp("2026-09-01T00:00:00Z")
    end = report.parse_timestamp("2026-09-01T02:00:00Z")
    calls = []

    def runner(command, attempts):
        calls.append((command, attempts))
        if len(calls) == 1:
            return json.dumps([{"id": f"capped-{index}"} for index in range(1000)])
        return json.dumps([{"id": "shared"}, {"id": f"slice-{len(calls)}"}])

    logs, flags = report.fetch_render_logs(["api", "worker"], start, end, runner)
    assert {item["id"] for item in logs} == {"shared", "slice-2", "slice-3"}
    assert len(calls) == 3
    assert all(attempts == 2 for _, attempts in calls)
    assert flags == []


def test_render_log_fetch_flags_an_irreducibly_capped_slice():
    report = load_report()
    start = report.parse_timestamp("2026-09-01T00:00:00Z")
    end = start + report.timedelta(seconds=30)

    def runner(_command, _attempts):
        return json.dumps([{"id": f"log-{index}"} for index in range(1000)])

    logs, flags = report.fetch_render_logs(["api", "worker"], start, end, runner)
    assert len(logs) == 1000
    assert "remained capped" in flags[0]


def test_command_runner_retries_once(monkeypatch):
    report = load_report()
    responses = [
        SimpleNamespace(returncode=1, stdout="", stderr="temporary"),
        SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    ]
    monkeypatch.setattr(report.subprocess, "run", lambda *_args, **_kwargs: responses.pop(0))
    assert report.run_command(["tool"], 2) == "ok"


def test_command_runner_stops_after_bounded_retry(monkeypatch):
    report = load_report()
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(returncode=1, stdout="", stderr="temporary")

    monkeypatch.setattr(report.subprocess, "run", fail)
    with pytest.raises(report.CommandError, match="temporary"):
        report.run_command(["tool"], 2)
    assert len(calls) == 2


def test_neon_operation_fetch_paginates_past_requested_start():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T00:00:00Z")
    calls = []
    pages = [
        {
            "operations": [
                operation("new", "endpoint", "suspend_compute", "2026-09-03T00:00:00Z")
            ],
            "pagination": {"cursor": "next"},
        },
        {
            "operations": [
                operation("old", "endpoint", "start_compute", "2026-09-01T23:00:00Z")
            ],
            "pagination": {},
        },
    ]

    def runner(command, attempts):
        calls.append((command, attempts))
        return json.dumps(pages.pop(0))

    operations, flags = report.fetch_neon_operations(start, runner)
    assert {item["id"] for item in operations} == {"new", "old"}
    assert "cursor=next" in calls[1][0]
    assert flags == []


def test_lifecycle_pairs_clips_open_intervals_and_multiple_endpoints():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T01:00:00Z")
    end = report.parse_timestamp("2026-09-02T05:00:00Z")
    operations = [
        operation("a0", "a", "start_compute", "2026-09-02T00:00:00Z"),
        operation("a1", "a", "suspend_compute", "2026-09-02T02:00:00Z"),
        operation("a2", "a", "start_compute", "2026-09-02T03:00:00Z"),
        operation("b1", "b", "start_compute", "2026-09-02T02:00:00Z"),
        operation("b2", "b", "suspend_compute", "2026-09-02T03:00:00Z"),
    ]
    summary = report.build_lifecycle_summary(operations, start, end)
    assert summary.active_hours == pytest.approx(4.0)
    assert len(summary.starts) == 2
    assert summary.flags == []


def test_lifecycle_includes_start_boundary_and_excludes_end_boundary():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T01:00:00Z")
    end = report.parse_timestamp("2026-09-02T03:00:00Z")
    operations = [
        operation("start", "a", "start_compute", "2026-09-02T01:00:00Z"),
        operation("end", "a", "suspend_compute", "2026-09-02T03:00:00Z"),
    ]
    summary = report.build_lifecycle_summary(operations, start, end)
    assert summary.active_hours == pytest.approx(2)
    assert summary.starts == [start]
    assert summary.flags == []


def test_lifecycle_infers_missing_start_and_flags_malformed_sequences():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T01:00:00Z")
    end = report.parse_timestamp("2026-09-02T03:00:00Z")
    operations = [
        operation("suspend", "a", "suspend_compute", "2026-09-02T02:00:00Z"),
        operation("start-1", "b", "start_compute", "2026-09-02T01:30:00Z"),
        operation("start-2", "b", "start_compute", "2026-09-02T02:00:00Z"),
    ]
    summary = report.build_lifecycle_summary(operations, start, end)
    assert summary.active_hours == pytest.approx(2.5)
    assert any("first appears as a suspension" in flag for flag in summary.flags)
    assert any("consecutive start" in flag for flag in summary.flags)


def test_neon_metrics_calculate_projection_and_preserve_missing_counters():
    report = load_report()
    captured = report.parse_timestamp("2026-09-06T00:00:00Z")
    metrics = report.neon_metrics(
        {
            "cpu_used_sec": 3600,
            "active_time_seconds": 14400,
            "consumption_period_start": "2026-09-01T00:00:00Z",
            "consumption_period_end": "2026-09-11T00:00:00Z",
        },
        captured,
    )
    assert metrics["cpu_hours"] == 1
    assert metrics["active_hours"] == 4
    assert metrics["average_cu"] == 0.25
    assert metrics["projection"] == 2

    missing = report.neon_metrics({}, captured)
    assert missing["cpu_hours"] is None
    assert missing["average_cu"] is None
    assert missing["projection"] is None


def test_collect_neon_marks_missing_counters_partial(monkeypatch):
    report = load_report()
    monkeypatch.setattr(report.shutil, "which", lambda _name: "/tool")

    def runner(command, _attempts):
        if command[:3] == ["neon", "projects", "get"]:
            return json.dumps({"id": "project"})
        if command[:2] == ["neon", "api"]:
            return json.dumps(
                {
                    "operations": [
                        operation(
                            "old",
                            "endpoint",
                            "suspend_compute",
                            "2026-09-01T00:00:00Z",
                        )
                    ],
                    "pagination": {},
                }
            )
        return "{}"

    start = report.parse_timestamp("2026-09-02T00:00:00Z")
    result = report.collect_neon(start, start + report.timedelta(days=1), runner)
    assert result.status == "PARTIAL"
    assert any("cpu_used_sec" in flag for flag in result.flags)


def test_collect_neon_preserves_lifecycle_when_counters_fail(monkeypatch):
    report = load_report()
    monkeypatch.setattr(report.shutil, "which", lambda _name: "/tool")

    def runner(command, _attempts):
        if command[:3] == ["neon", "projects", "get"]:
            raise report.CommandError("counter failure")
        if command[:2] == ["neon", "api"]:
            return json.dumps(
                {
                    "operations": [
                        operation(
                            "old",
                            "endpoint",
                            "start_compute",
                            "2026-09-01T23:00:00Z",
                        ),
                        operation(
                            "stop",
                            "endpoint",
                            "suspend_compute",
                            "2026-09-02T01:00:00Z",
                        ),
                    ],
                    "pagination": {},
                }
            )
        return "{}"

    start = report.parse_timestamp("2026-09-02T00:00:00Z")
    result = report.collect_neon(start, start + report.timedelta(days=1), runner)
    assert result.status == "PARTIAL"
    assert result.lifecycle.active_hours == pytest.approx(1)
    assert any("counter failure" in flag for flag in result.flags)


def test_collect_render_returns_partial_for_ranges_beyond_retention(monkeypatch):
    report = load_report()
    monkeypatch.setattr(report.shutil, "which", lambda _name: "/tool")
    services = [
        render_service("sports-alerts-platform-api", "web_service"),
        render_service("sports-alerts-platform-worker", "background_worker"),
    ]

    def runner(command, _attempts):
        if command[:2] == ["render", "services"]:
            return json.dumps(services)
        return "[]"

    start = report.parse_timestamp("2026-09-01T00:00:00Z")
    result = report.collect_render(start, start + report.timedelta(days=8), 8, runner)
    assert result.status == "PARTIAL"
    assert any("exceeds Render's 7-day" in flag for flag in result.flags)
    assert any("No Render" in flag for flag in result.flags)


def test_collect_render_marks_empty_logs_partial(monkeypatch):
    report = load_report()
    monkeypatch.setattr(report.shutil, "which", lambda _name: "/tool")
    services = [
        render_service("sports-alerts-platform-api", "web_service"),
        render_service("sports-alerts-platform-worker", "background_worker"),
    ]

    def runner(command, _attempts):
        if command[:2] == ["render", "services"]:
            return json.dumps(services)
        return "[]"

    start = report.parse_timestamp("2026-09-02T00:00:00Z")
    result = report.collect_render(start, start + report.timedelta(days=1), 1, runner)
    assert result.status == "PARTIAL"
    assert result.logs == []
    assert any("No Render" in flag for flag in result.flags)


def test_cross_source_coverage_flags_unattributed_lifecycle_activity():
    report = load_report()
    start = report.parse_timestamp("2026-09-01T00:00:00Z")
    end = report.parse_timestamp("2026-09-02T00:00:00Z")
    neon = report.NeonReport(
        status="COMPLETE",
        lifecycle=report.LifecycleSummary(
            intervals=[(start, report.parse_timestamp("2026-09-01T02:00:00Z"))]
        ),
        lifecycle_available=True,
    )
    render = report.RenderReport(
        status="COMPLETE",
        windows=[("2026-09-01T03:00:00Z", "2026-09-01T03:05:00Z")],
    )
    report.reconcile_coverage(neon, render, start, end)
    assert render.status == "PARTIAL"
    assert "2.00 active hours before" in render.flags[0]


def test_report_labels_evidence_and_partial_sources():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T00:00:00Z")
    end = report.parse_timestamp("2026-09-03T00:00:00Z")
    neon = report.NeonReport(
        status="COMPLETE",
        project={
            "cpu_used_sec": 3600,
            "active_time_seconds": 14400,
            "consumption_period_start": "2026-09-01T00:00:00Z",
            "consumption_period_end": "2026-10-01T00:00:00Z",
        },
        lifecycle=report.LifecycleSummary(intervals=[(start, end)]),
        lifecycle_available=True,
    )
    render = report.RenderReport(status="UNAVAILABLE", flags=["Render unavailable"])
    output = report.build_report(end, start, 1, neon, render, lambda *_args: "")
    assert "Sources: Neon=COMPLETE; Render=UNAVAILABLE" in output
    assert "Neon counters (exact as reported by Neon" in output
    assert "Lifecycle-derived compute-active hours: 24.000" in output
    assert "Estimated CU-hours: 6.000" in output
    assert "- Render unavailable" in output


def test_report_does_not_render_missing_lifecycle_or_logs_as_zero():
    report = load_report()
    start = report.parse_timestamp("2026-09-02T07:00:00Z")
    end = report.parse_timestamp("2026-09-03T07:00:00Z")
    neon = report.NeonReport(
        status="PARTIAL",
        project={"cpu_used_sec": 3600, "active_time_seconds": 14400},
        flags=["Neon lifecycle history is unavailable"],
    )
    render = report.RenderReport(status="PARTIAL", flags=["No Render summaries"])
    output = report.build_report(end, start, 1, neon, render, lambda *_args: "")
    assert "Neon lifecycle: unavailable" in output
    assert "Lifecycle-derived compute-active hours: unavailable" in output
    assert "2026-09-02 | full | unavailable | unavailable | unavailable | unavailable" in output


def test_main_exit_status_and_invalid_days(monkeypatch, capsys):
    report = load_report()
    monkeypatch.setattr(
        report,
        "collect_neon",
        lambda *_args: report.NeonReport(status="COMPLETE"),
    )
    monkeypatch.setattr(
        report,
        "collect_render",
        lambda *_args: report.RenderReport(status="PARTIAL", flags=["partial"]),
    )
    monkeypatch.setattr(report, "build_report", lambda *_args: "report")
    assert report.main(["--days", "1"]) == 1
    assert capsys.readouterr().out == "report\n"

    with pytest.raises(SystemExit):
        report.parse_args(["--days", "0"])
