"""Regression: /stop must hold on scheduler-OFF accounts (v3.1 #5).

Found live 2026-06-10 03:02: with scheduling explicitly off, the disabled path
ignored stop overrides, so the watchdog relaunched a /stop'ed farm ~1 minute
later. evaluate() now honors a stop override regardless of enablement (run
overrides stay meaningless when disabled — disabled already means always-run).
"""

from datetime import datetime, timedelta

from brawlfarm.core.scheduler import evaluate

NOW = datetime(2026, 6, 10, 3, 0, 0)


def test_disabled_honors_stop_override():
    ov = {
        "mode": "stop",
        "until": (NOW + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    d = evaluate(NOW, None, 0, ov, enabled=False)
    assert d["state"] == "stop"
    assert d["reason"] == "override_stop"
    assert d["enabled"] is False


def test_disabled_run_override_is_meaningless():
    ov = {
        "mode": "run",
        "until": (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    d = evaluate(NOW, None, 0, ov, enabled=False)
    assert d["state"] == "run"
    assert d["reason"] == "disabled"


def test_disabled_no_override_unchanged():
    d = evaluate(NOW, None, 0, None, enabled=False)
    assert (d["state"], d["reason"]) == ("run", "disabled")


def test_disabled_malformed_override_fails_open():
    d = evaluate(NOW, None, 0, {"mode": "stop"}, enabled=False)  # no 'until'
    assert d["state"] == "run"  # never strand a farm on bad state
