# VaxSchedule

Vaccination cohort and dose scheduling system: Software Engineering (UE24CS341A) Jackfruit mini-project.

Citizens register and book doses, officers record the dose and batch given, and anyone can verify a
signed QR certificate.

## Features
| ID | Feature | Module | Owner |
|---|---|---|---|
| FR-001 | Citizen registration and login | `registration.py` | @bhardwajkishan |
| FR-002 | Slot search by PIN, booking and cancelling | `scheduling.py` | @barunaniket |
| FR-003 | Dose-interval rule (Covaxin 28 days, Covishield 84 days, same vaccine) | `rules.py`, `scheduling.py` | @barunaniket |
| FR-004 | Officer console: publish slots, record doses | `records.py` | @Ekaaaasss02 |
| FR-005 | HMAC-signed QR certificate and public verification | `certificates.py` | @bhardwajkishan |

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python run.py --seed          # http://127.0.0.1:5000, officer code: officer123
```
Configuration comes from environment variables: `SECRET_KEY`, `CERT_SECRET`, `OFFICER_CODE`,
`DATABASE`, and `TODAY` (fixes the date, for demos and tests).

## Docker
```bash
docker build -t vaxschedule .
docker run -p 5000:5000 -e SECRET_KEY=change-me -e CERT_SECRET=change-me -e OFFICER_CODE=change-me vaxschedule
```

## Quality gates (run in CI on every push and PR)
```bash
flake8 vaccination tests run.py
pylint vaccination run.py --disable=C0114 --fail-under=9.5
bandit -r vaccination run.py
pytest --cov=vaccination --cov-branch --cov-fail-under=90
```

## Architecture
A layered modular monolith: `web.py` (routes) → one module per feature → `db.py` (SQLite).
Modules call each other only through public functions and never touch each other's SQL.
See `docs/` and the Technical Design for details.
