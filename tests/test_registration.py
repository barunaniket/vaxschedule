"""Unit tests for registration.py (UT-01 to UT-11)."""
from datetime import date

import pytest

from vaccination import registration
from vaccination.rules import NotFoundError, ValidationError

TODAY = date(2026, 11, 2)
VALID = {"name": "Asha Rao", "dob": "1990-05-17",
         "id_number": "abcd1234", "mobile": "9876543210"}


def register(conn, **changes):
    data = {**VALID, **changes}
    return registration.register_citizen(conn, today=TODAY, **data)


def test_register_valid_citizen(conn):  # UT-01
    citizen_id = register(conn, name="  Asha Rao ")
    row = registration.get_citizen(conn, citizen_id)
    assert row["name"] == "Asha Rao"
    assert row["id_number"] == "ABCD1234"
    assert row["dob"] == "1990-05-17"


def test_register_defaults_today(conn):
    citizen_id = registration.register_citizen(conn, **VALID)
    assert citizen_id > 0


@pytest.mark.parametrize("changes, message", [
    ({"name": " "}, "Name must be"),                       # UT-02
    ({"name": None}, "Name must be"),
    ({"id_number": "AB12"}, "ID number"),                  # UT-03
    ({"id_number": "ABCD-1234"}, "ID number"),             # UT-04
    ({"mobile": "12345"}, "Mobile number must be 10"),     # UT-05
    ({"dob": "2027-01-01"}, "future"),                     # UT-06
    ({"dob": "17-05-1990"}, "Invalid date"),               # UT-07
    ({"dob": "2010-05-17"}, "at least 18"),                # UT-08
])
def test_register_rejects_invalid_input(conn, changes, message):
    with pytest.raises(ValidationError, match=message):
        register(conn, **changes)


def test_register_turning_18_today_is_allowed(conn):
    assert register(conn, dob="2008-11-02") > 0


def test_duplicate_id_is_refused(conn):  # UT-09
    register(conn)
    with pytest.raises(ValidationError, match="already registered"):
        register(conn, id_number="ABCD1234", mobile="9000000000")


def test_get_missing_citizen(conn):  # UT-10
    with pytest.raises(NotFoundError, match="Citizen 999 not found"):
        registration.get_citizen(conn, 999)


def test_login(conn):  # UT-11
    citizen_id = register(conn)
    row = registration.find_by_login(conn, " abcd1234 ", "9876543210")
    assert row["id"] == citizen_id
    with pytest.raises(NotFoundError, match="No citizen"):
        registration.find_by_login(conn, "ABCD1234", "9000000000")
    with pytest.raises(NotFoundError):
        registration.find_by_login(conn, None, None)
