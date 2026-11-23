"""Unit tests for certificates.py (UT-C1 to UT-C6)."""
import base64
import json
import time

import pytest

from vaccination import certificates
from vaccination.rules import NotFoundError, RuleViolation

from .conftest import add_dose

SECRET = "test-cert"


def token_for(conn, citizen_id):
    certificates.issue_certificate(conn, SECRET, citizen_id)
    return certificates.qr_token(
        certificates.latest_certificate(conn, citizen_id))


def test_no_doses_no_certificate(conn, citizen):  # UT-C1
    with pytest.raises(RuleViolation, match="No doses"):
        certificates.issue_certificate(conn, SECRET, citizen)
    with pytest.raises(NotFoundError, match="No certificate"):
        certificates.latest_certificate(conn, citizen)


def test_partial_after_one_dose(conn, citizen):  # UT-C2
    add_dose(conn, citizen, "Covaxin", "2026-11-02", batch="B-77")
    token = token_for(conn, citizen)
    data = certificates.verify_token(SECRET, token)
    assert data["status"] == "PARTIALLY VACCINATED"
    assert data["id_last4"] == "1234"
    assert data["doses"] == [{"n": 1, "date": "2026-11-02", "batch": "B-77"}]
    assert "<svg" in certificates.qr_svg(token)


def test_full_after_two_doses(conn, citizen):  # UT-C3
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    add_dose(conn, citizen, "Covaxin", "2026-11-30", dose_number=2)
    data = certificates.verify_token(SECRET, token_for(conn, citizen))
    assert data["status"] == "FULLY VACCINATED"
    assert len(data["doses"]) == 2


def test_latest_certificate_is_newest(conn, citizen):
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    first = certificates.issue_certificate(conn, SECRET, citizen)
    second = certificates.issue_certificate(conn, SECRET, citizen)
    assert second > first
    assert certificates.latest_certificate(conn, citizen)["id"] == second


def _forged_token(conn, citizen):
    """Same signature, but the payload says FULLY VACCINATED."""
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    token = token_for(conn, citizen)
    body, signature = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(body + "=="))
    data["status"] = "FULLY VACCINATED"
    forged = base64.urlsafe_b64encode(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
    return forged.decode().rstrip("=") + "." + signature


@pytest.mark.parametrize("token", [
    "", None, "no-dot", ".abc", "abc.", "@@@.abc", "gA.sig", "abc.ünïcode",
])
def test_garbage_tokens_are_invalid(token):  # UT-C4
    assert certificates.verify_token(SECRET, token) is None


def test_tampered_payload_is_invalid(conn, citizen):
    assert certificates.verify_token(
        SECRET, _forged_token(conn, citizen)) is None


def test_wrong_key_is_invalid(conn, citizen):  # UT-C5
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    token = token_for(conn, citizen)
    assert certificates.verify_token("another-key", token) is None
    assert certificates.verify_token(SECRET.encode(), token) is not None


def test_verification_is_fast(conn, citizen):  # UT-C6 / NFR-001
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    token = token_for(conn, citizen)
    conn.close()  # verification must not need the database
    start = time.perf_counter()
    for _ in range(1000):
        assert certificates.verify_token(SECRET, token) is not None
    average_ms = (time.perf_counter() - start) * 1000 / 1000
    assert average_ms < 150
