"""System validation tests (ST-01 to ST-15) through the Flask test client."""
from vaccination import scheduling

from .conftest import (TODAY_DATE, add_citizen, add_dose, login_as_citizen,
                       setup_slots)
from .conftest import login_as_officer


def page(response):
    return response.get_data(as_text=True)


def test_home_page(client):
    assert "Vaccination booking portal" in page(client.get("/"))


# --- Module 1: registration -------------------------------------------------
REGISTER = {"name": "Asha Rao", "dob": "1990-05-17",
            "id_number": "ABCD1234", "mobile": "9876543210"}


def test_st01_register_opens_dashboard(client):
    html = page(client.post("/register", data=REGISTER,
                            follow_redirects=True))
    assert "Registration successful" in html
    assert "Welcome, Asha Rao" in html


def test_st02_invalid_mobile(client):
    html = page(client.post("/register", data={**REGISTER, "mobile": "123"},
                            follow_redirects=True))
    assert "Mobile number must be 10 digits" in html


def test_st03_logout_and_login(client):
    client.post("/register", data=REGISTER)
    html = page(client.get("/logout", follow_redirects=True))
    assert "logged out" in html
    assert "Please log in first" in page(
        client.get("/citizen", follow_redirects=True))
    html = page(client.post("/login", data={
        "id_number": "abcd1234", "mobile": "9876543210"},
        follow_redirects=True))
    assert "Welcome, Asha Rao" in html
    client.get("/logout")
    html = page(client.post("/login", data={
        "id_number": "ABCD1234", "mobile": "9000000000"},
        follow_redirects=True))
    assert "No citizen" in html


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


# --- Module 3: officer records ----------------------------------------------
def test_st04_pages_need_login(client):
    for url in ["/citizen", "/officer"]:
        html = page(client.get(url, follow_redirects=True))
        assert "Please log in first" in html


def test_st05_citizen_cannot_open_officer_console(client, app_conn):
    login_as_citizen(client, add_citizen(app_conn))
    html = page(client.get("/officer", follow_redirects=True))
    assert "Please log in first" in html


def test_st06_officer_login(client):
    assert "Access code" in page(client.get("/officer/login"))
    html = page(client.post("/officer/login", data={"code": "nope"},
                            follow_redirects=True))
    assert "Wrong officer code" in html
    html = page(client.post("/officer/login", data={"code": "officer-test"},
                            follow_redirects=True))
    assert "Officer console" in html


def test_st11_publish_slot(client, app_conn):
    centre, _ = setup_slots(app_conn)
    login_as_officer(client)
    form = {"centre_id": centre, "date": "2026-11-09", "vaccine": "Covaxin",
            "capacity": "30"}
    html = page(client.post("/officer/slot", data=form,
                            follow_redirects=True))
    assert "Slot published" in html
    assert len(scheduling.search_slots(app_conn, from_day="2026-11-09")) == 1
    html = page(client.post("/officer/slot", data={**form, "capacity": "0"},
                            follow_redirects=True))
    assert "Capacity must be positive" in html


def test_officer_console_lists_bookings(client, app_conn):
    _, slot = setup_slots(app_conn)
    booking = scheduling.book_slot(
        app_conn, add_citizen(app_conn), slot, TODAY_DATE)
    login_as_officer(client)
    html = page(client.get("/officer"))
    assert "Asha Rao" in html
    assert f"/officer/record/{booking}" in html
    assert "No bookings on 2026-11-03" in page(
        client.get("/officer?day=2026-11-03"))
    html = page(client.get("/officer?day=garbage"))
    assert "Invalid date" in html


def test_officer_records_dose(client, app_conn):
    _, slot = setup_slots(app_conn)
    citizen = add_citizen(app_conn)
    booking = scheduling.book_slot(app_conn, citizen, slot, TODAY_DATE)
    login_as_officer(client)
    html = page(client.post(f"/officer/record/{booking}",
                            data={"batch": "b-7", "day": "2026-11-02"},
                            follow_redirects=True))
    assert "Dose recorded" in html
    assert scheduling.doses_taken(app_conn, citizen)[0]["batch"] == "B-7"


def test_st13_record_missing_booking(client):
    login_as_officer(client)
    html = page(client.post("/officer/record/42", data={"batch": "B-1"},
                            follow_redirects=True))
    assert "Booking 42 not found" in html
