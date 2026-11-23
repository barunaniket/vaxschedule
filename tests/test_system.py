"""System validation tests (ST-01 to ST-15) through the Flask test client."""
from vaccination import scheduling

from .conftest import (TODAY_DATE, add_citizen, add_dose, login_as_citizen,
                       setup_slots)


def page(response):
    return response.get_data(as_text=True)


def test_home_page(client):
    assert "Vaccination booking portal" in page(client.get("/"))


# --- Module 2: booking ------------------------------------------------------
def test_dashboard_shows_slots_and_books(client, app_conn):
    _, slot = setup_slots(app_conn)
    login_as_citizen(client, add_citizen(app_conn))
    html = page(client.get("/citizen"))
    assert "Welcome, Asha Rao" in html
    assert "NOT VACCINATED" in html
    assert "PHC Banashankari" in html
    html = page(client.post(f"/book/{slot}", follow_redirects=True))
    assert "Slot booked" in html
    assert "Your booking" in html


def test_st08_dose_two_too_early(client, app_conn):
    centre, _ = setup_slots(app_conn)
    citizen = add_citizen(app_conn)
    add_dose(app_conn, citizen, "Covaxin", "2026-10-25")
    early = scheduling.add_slot(app_conn, centre, "2026-11-02", "Covaxin", 5)
    login_as_citizen(client, citizen)
    html = page(client.get("/citizen"))
    assert "PARTIALLY VACCINATED" in html
    assert "Next dose from <strong>2026-11-22" in html
    html = page(client.post(f"/book/{early}", follow_redirects=True))
    assert "Dose not allowed before 2026-11-22" in html


def test_dashboard_when_fully_vaccinated(client, app_conn):
    citizen = add_citizen(app_conn)
    add_dose(app_conn, citizen, "Covaxin", "2026-09-01")
    add_dose(app_conn, citizen, "Covaxin", "2026-10-01", dose_number=2)
    login_as_citizen(client, citizen)
    html = page(client.get("/citizen"))
    assert "FULLY VACCINATED" in html
    assert "Next dose from" not in html


def test_st09_cancel_twice(client, app_conn):
    _, slot = setup_slots(app_conn)
    citizen = add_citizen(app_conn)
    booking = scheduling.book_slot(app_conn, citizen, slot, TODAY_DATE)
    login_as_citizen(client, citizen)
    html = page(client.post(f"/cancel/{booking}", follow_redirects=True))
    assert "Booking cancelled" in html
    html = page(client.post(f"/cancel/{booking}", follow_redirects=True))
    assert "Only active bookings can be cancelled" in html


def test_st10_cannot_cancel_someone_elses_booking(client, app_conn):
    _, slot = setup_slots(app_conn)
    owner = add_citizen(app_conn)
    booking = scheduling.book_slot(app_conn, owner, slot, TODAY_DATE)
    login_as_citizen(client, add_citizen(app_conn, id_number="ZZZZ9999"))
    html = page(client.post(f"/cancel/{booking}", follow_redirects=True))
    assert f"Booking {booking} not found" in html
    assert scheduling.active_booking(app_conn, owner) is not None


def test_st12_book_missing_slot(client, app_conn):
    login_as_citizen(client, add_citizen(app_conn))
    html = page(client.post("/book/999", follow_redirects=True))
    assert "Slot 999 not found" in html


def test_st14_pin_filter(client, app_conn):
    setup_slots(app_conn)
    login_as_citizen(client, add_citizen(app_conn))
    assert "PHC Banashankari" in page(client.get("/citizen?pincode=560085"))
    assert "No free slots" in page(client.get("/citizen?pincode=111111"))
