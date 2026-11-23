"""Database schema and connection helper (SQLite)."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS citizens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  dob TEXT NOT NULL,
  id_number TEXT NOT NULL UNIQUE,
  mobile TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS centres (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  district TEXT NOT NULL,
  pincode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  centre_id INTEGER NOT NULL REFERENCES centres(id),
  date TEXT NOT NULL,
  vaccine TEXT NOT NULL,
  capacity INTEGER NOT NULL,
  booked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  citizen_id INTEGER NOT NULL REFERENCES citizens(id),
  slot_id INTEGER NOT NULL REFERENCES slots(id),
  dose_number INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'BOOKED'
);
CREATE TABLE IF NOT EXISTS doses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  citizen_id INTEGER NOT NULL REFERENCES citizens(id),
  booking_id INTEGER REFERENCES bookings(id),
  dose_number INTEGER NOT NULL,
  vaccine TEXT NOT NULL,
  batch TEXT NOT NULL,
  date_given TEXT NOT NULL,
  UNIQUE (citizen_id, dose_number)
);
CREATE TABLE IF NOT EXISTS certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  citizen_id INTEGER NOT NULL REFERENCES citizens(id),
  payload TEXT NOT NULL,
  signature TEXT NOT NULL,
  issued_at TEXT NOT NULL
);
"""


def connect(path):
    """Open a connection, enable foreign keys and create the schema."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
