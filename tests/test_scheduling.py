"""Unit tests for scheduling.py (UT-B1 to UT-B11)."""
import pytest

from vaccination import scheduling
from vaccination.rules import NotFoundError, RuleViolation, ValidationError

from .conftest import TODAY_DATE, add_citizen, add_dose


def slot_row(conn, slot_id):
    return conn.execute(
        "SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()


@pytest.mark.parametrize("name, district, pincode, message", [
    ("", "Bengaluru", "560085", "required"),
    ("PHC", None, "560085", "required"),
    ("PHC", "Bengaluru", "5600", "6 digits"),
    ("PHC", "Bengaluru", "56008A", "6 digits"),
])
def test_add_centre_validation(conn, name, district, pincode, message):
    with pytest.raises(ValidationError, match=message):  # UT-B1
        scheduling.add_centre(conn, name, district, pincode)


def test_list_centres(conn, centre):
    assert [c["id"] for c in scheduling.list_centres(conn)] == [centre]


@pytest.mark.parametrize("capacity, message", [
    (0, "positive"), (-5, "positive"), ("ten", "whole number"),
    (None, "whole number"),
])
def test_add_slot_bad_capacity(conn, centre, capacity, message):
    with pytest.raises(ValidationError, match=message):  # UT-B2
        scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", capacity)


def test_add_slot_unknown_vaccine(conn, centre):
    with pytest.raises(ValidationError, match="Unknown vaccine"):
        scheduling.add_slot(conn, centre, "2026-11-05", "Sputnik", 10)


def test_add_slot_missing_centre(conn):
    with pytest.raises(NotFoundError, match="Centre 42 not found"):
        scheduling.add_slot(conn, 42, "2026-11-05", "Covaxin", 10)


def test_search_slots(conn, centre):  # UT-B3
    other = scheduling.add_centre(conn, "CHC E-City", "Bengaluru", "560100")
    scheduling.add_slot(conn, centre, "2026-11-01", "Covaxin", 10)
    scheduling.add_slot(conn, other, "2026-11-02", "Covaxin", 10)
    scheduling.add_slot(conn, other, "2026-11-03", "Covishield", 10)
    assert len(scheduling.search_slots(conn)) == 3
    by_pin = scheduling.search_slots(conn, pincode="560085")
    assert [s["centre"] for s in by_pin] == ["PHC Banashankari"]
    assert len(scheduling.search_slots(conn, from_day="2026-11-02")) == 2
    assert scheduling.search_slots(conn, pincode="111111") == []


def test_search_hides_full_slots(conn, centre, citizen):
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 1)
    scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    assert scheduling.search_slots(conn) == []


def test_book_dose_one(conn, centre, citizen):  # UT-B4
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 10)
    booking_id = scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    booking = scheduling.active_booking(conn, citizen)
    assert booking["id"] == booking_id
    assert booking["dose_number"] == 1
    assert booking["centre"] == "PHC Banashankari"
    assert slot_row(conn, slot)["booked"] == 1


def test_book_defaults_to_real_today(conn, centre, citizen):
    slot = scheduling.add_slot(conn, centre, "2999-01-01", "Covaxin", 10)
    assert scheduling.book_slot(conn, citizen, slot) > 0


def test_book_missing_citizen_or_slot(conn, centre, citizen):  # UT-B5
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 10)
    with pytest.raises(NotFoundError, match="Citizen 99 not found"):
        scheduling.book_slot(conn, 99, slot, today=TODAY_DATE)
    with pytest.raises(NotFoundError, match="Slot 99 not found"):
        scheduling.book_slot(conn, citizen, 99, today=TODAY_DATE)


def test_book_past_slot(conn, centre, citizen):
    slot = scheduling.add_slot(conn, centre, "2026-11-01", "Covaxin", 10)
    with pytest.raises(RuleViolation, match="past"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_book_full_slot(conn, centre, citizen):  # UT-B6
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 1)
    other = add_citizen(conn, id_number="ZZZZ9999")
    scheduling.book_slot(conn, other, slot, today=TODAY_DATE)
    with pytest.raises(RuleViolation, match="full"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_second_active_booking_refused(conn, centre, citizen):
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 10)
    scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    with pytest.raises(RuleViolation, match="active booking"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_dose_two_too_early(conn, centre, citizen):  # UT-B7 / FR-003
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    slot = scheduling.add_slot(conn, centre, "2026-11-10", "Covaxin", 10)
    with pytest.raises(RuleViolation,
                       match="Dose not allowed before 2026-11-30"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_dose_two_on_allowed_day_then_fully_vaccinated(
        conn, centre, citizen):  # UT-B8
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    slot = scheduling.add_slot(conn, centre, "2026-11-30", "Covaxin", 10)
    scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    assert scheduling.active_booking(conn, citizen)["dose_number"] == 2

    conn.execute("UPDATE bookings SET status = 'COMPLETED'")
    add_dose(conn, citizen, "Covaxin", "2026-11-30", dose_number=2)
    later = scheduling.add_slot(conn, centre, "2027-06-01", "Covaxin", 10)
    with pytest.raises(RuleViolation, match="fully vaccinated"):
        scheduling.book_slot(conn, citizen, later, today=TODAY_DATE)


def test_dose_two_different_vaccine(conn, centre, citizen):  # UT-B9
    add_dose(conn, citizen, "Covaxin", "2026-11-02")
    slot = scheduling.add_slot(conn, centre, "2027-03-01", "Covishield", 10)
    with pytest.raises(RuleViolation, match="same vaccine"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)


def test_cancel_booking(conn, centre, citizen):  # UT-B10
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 10)
    booking_id = scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    scheduling.cancel_booking(conn, booking_id)
    assert slot_row(conn, slot)["booked"] == 0
    assert scheduling.active_booking(conn, citizen) is None
    with pytest.raises(RuleViolation, match="Only active bookings"):
        scheduling.cancel_booking(conn, booking_id)
    with pytest.raises(NotFoundError, match="Booking 99 not found"):
        scheduling.cancel_booking(conn, 99)


def test_race_on_last_place(conn, centre, citizen, monkeypatch):  # UT-B11
    """Another citizen takes the last place between the check and UPDATE."""
    slot = scheduling.add_slot(conn, centre, "2026-11-05", "Covaxin", 1)
    real_active_booking = scheduling.active_booking

    def fill_slot_then_check(connection, citizen_id):
        connection.execute("UPDATE slots SET booked = capacity WHERE id = ?",
                           (slot,))
        return real_active_booking(connection, citizen_id)

    monkeypatch.setattr(scheduling, "active_booking", fill_slot_then_check)
    with pytest.raises(RuleViolation, match="full"):
        scheduling.book_slot(conn, citizen, slot, today=TODAY_DATE)
    count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    assert count == 0
