"""Unit tests for records.py (UT-D1 to UT-D4)."""
import pytest

from vaccination import records, scheduling
from vaccination.rules import NotFoundError, RuleViolation, ValidationError

from .conftest import TODAY_DATE


@pytest.fixture
def booking(conn, centre, citizen):
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 10)
    return scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_bookings_for_day(conn, booking):  # UT-D1
    rows = records.bookings_for_day(conn, "2026-11-05")
    assert [r["id"] for r in rows] == [booking]
    assert rows[0]["name"] == "Asha Rao"
    assert rows[0]["centre"] == "PHC Banashankari"
    assert records.bookings_for_day(conn, "2026-11-06") == []


def test_cancelled_bookings_are_hidden(conn, booking):
    scheduling.cancel_booking(conn, booking)
    assert records.bookings_for_day(conn, "2026-11-05") == []


def test_record_dose(conn, citizen, booking):  # UT-D2
    records.record_dose(conn, booking, " b-77 ")
    dose = scheduling.doses_taken(conn, citizen)[0]
    assert dose["batch"] == "B-77"
    assert dose["date_given"] == "2026-11-05"
    assert dose["vaccine"] == "Covaxin"
    assert dose["booking_id"] == booking
    status = records.bookings_for_day(conn, "2026-11-05")[0]["status"]
    assert status == "COMPLETED"


def test_record_same_booking_twice(conn, booking):  # UT-D3
    records.record_dose(conn, booking, "B-1")
    with pytest.raises(RuleViolation, match="COMPLETED"):
        records.record_dose(conn, booking, "B-1")


@pytest.mark.parametrize("batch", ["", "   ", None])
def test_record_requires_batch(conn, booking, batch):  # UT-D4
    with pytest.raises(ValidationError, match="Batch number is required"):
        records.record_dose(conn, booking, batch)


def test_record_missing_booking(conn):
    with pytest.raises(NotFoundError, match="Booking 42 not found"):
        records.record_dose(conn, 42, "B-1")
