"""Tests for the seed script."""
from datetime import date

import run
from vaccination import scheduling


def test_seed_is_idempotent(conn):
    assert run.seed(conn, date(2026, 11, 2)) == 36
    assert run.seed(conn, date(2026, 11, 2)) == 0
    assert len(scheduling.search_slots(conn, pincode="560041")) == 12


def test_main_seeds_and_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE", str(tmp_path / "demo.db"))
    monkeypatch.setenv("TODAY", "2026-11-02")
    started = {}
    monkeypatch.setattr("flask.Flask.run",
                        lambda self, **kw: started.update(kw))
    run.main(["--seed", "--port", "5050"])
    assert started == {"host": "127.0.0.1", "port": 5050}
