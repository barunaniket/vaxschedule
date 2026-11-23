"""Shared fixtures. The date is fixed so the tests are repeatable."""
from datetime import date

import pytest

from vaccination import create_app, db

TODAY = "2026-11-02"
TODAY_DATE = date(2026, 11, 2)


def add_citizen(conn, name="Asha Rao", id_number="ABCD1234",
                mobile="9876543210", dob="1990-05-17"):
    """Insert a citizen directly, so tests don't depend on registration."""
    with conn:
        cur = conn.execute(
            "INSERT INTO citizens (name, dob, id_number, mobile) "
            "VALUES (?, ?, ?, ?)", (name, dob, id_number, mobile))
    return cur.lastrowid


def add_dose(conn, citizen_id, vaccine, day, dose_number=1, batch="B-1"):
    """Insert a dose directly (as if the officer had recorded it)."""
    with conn:
        conn.execute(
            "INSERT INTO doses (citizen_id, dose_number, vaccine, batch, "
            "date_given) VALUES (?, ?, ?, ?, ?)",
            (citizen_id, dose_number, vaccine, batch, day))


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def citizen(conn):
    return add_citizen(conn)


@pytest.fixture
def app():
    return create_app({
        "TESTING": True, "DATABASE": ":memory:", "TODAY": TODAY,
        "SECRET_KEY": "test", "CERT_SECRET": "test-cert",
        "OFFICER_CODE": "officer-test",
    })


@pytest.fixture
def app_conn(app):
    return app.extensions["db"]


@pytest.fixture
def client(app):
    return app.test_client()


def login_as_citizen(client, citizen_id, name="Asha Rao"):
    """Put a citizen session on the test client."""
    with client.session_transaction() as sess:
        sess["role"] = "citizen"
        sess["citizen_id"] = citizen_id
        sess["name"] = name


def login_as_officer(client):
    with client.session_transaction() as sess:
        sess["role"] = "officer"
