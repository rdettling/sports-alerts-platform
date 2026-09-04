import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_decodes_render_output_and_unions_activity_minutes():
    report = load_script("database_usage_report")
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
    log = {"message": "2026-09-04 INFO Database usage " + json.dumps(payload)}
    raw = json.dumps(log) + "\n" + json.dumps(log)
    totals, minutes, windows, revisions = report.summarize(
        list(report.decode_logs(raw))
    )
    assert totals["api:GET /games"]["connections"] == 2
    assert totals["api:GET /games"]["game_cache_hits"] == 4
    assert len(minutes["api:GET /games"]) == 1
    assert len(windows) == 2
    assert revisions == {"abc123"}
    assert list(report.decode_logs(json.dumps([log]))) == [log]
    assert (
        report.summarize(
            [{"message": "Database usage logging started interval_seconds=300"}]
        )[2]
        == []
    )


def test_snapshot_does_not_compare_other_projects_or_billing_periods(
    tmp_path, monkeypatch, capsys
):
    snapshot = load_script("neon_usage_snapshot")
    current = {
        "id": "project-a",
        "consumption_period_start": "2026-09-01T00:00:00Z",
        "cpu_used_sec": 100,
        "active_time_seconds": 400,
    }
    for index, (project, period) in enumerate(
        [
            ("project-b", current["consumption_period_start"]),
            ("project-a", "2026-08-01T00:00:00Z"),
        ]
    ):
        (tmp_path / f"neon-usage-2026080{index}.json").write_text(
            json.dumps({"project_id": project, "consumption_period_start": period})
        )
    monkeypatch.setattr(snapshot, "run", lambda cmd: json.dumps(current))
    monkeypatch.setattr(
        "sys.argv",
        ["snapshot", "--project-id", "project-a", "--out-dir", str(tmp_path)],
    )
    snapshot.main()
    assert "Need one more snapshot" in capsys.readouterr().out


def test_snapshot_missing_counters_are_not_reported_as_zero(
    tmp_path, monkeypatch, capsys
):
    snapshot = load_script("neon_usage_snapshot")
    previous = {
        "project_id": "project-a",
        "consumption_period_start": "2026-09-01T00:00:00Z",
        "captured_at": "2026-09-01T01:00:00Z",
        "cpu_used_sec": 0,
        "active_time_sec": 0,
    }
    (tmp_path / "neon-usage-20260901T010000Z.json").write_text(json.dumps(previous))
    monkeypatch.setattr(
        snapshot,
        "run",
        lambda cmd: json.dumps(
            {
                "id": "project-a",
                "consumption_period_start": previous["consumption_period_start"],
            }
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["snapshot", "--project-id", "project-a", "--out-dir", str(tmp_path)],
    )
    snapshot.main()
    assert "unavailable (not zero)" in capsys.readouterr().out


def test_report_command_prints_hourly_attribution_without_database_access(
    monkeypatch, capsys
):
    from types import SimpleNamespace

    report = load_script("database_usage_report")
    payload = {
        "revision": "abc123",
        "window_start": "2026-09-04T00:00:00Z",
        "window_end": "2026-09-04T00:05:00Z",
        "sources": {
            "worker:competition_scan": {
                "connections": 1,
                "db_minutes": ["2026-09-04T00:01Z"],
            }
        },
    }
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(
            stdout=json.dumps({"message": "Database usage " + json.dumps(payload)})
        )

    monkeypatch.setattr(report.subprocess, "run", run)
    monkeypatch.setattr("sys.argv", ["report", "--resources", "api,worker"])
    report.main()
    output = capsys.readouterr().out
    assert "2026-09-04T00:00Z | worker:competition_scan=1" in output
    assert "not Neon awake hours" in output
    assert calls[0][:2] == ["render", "logs"]
    assert "Database usage {" in calls[0]
