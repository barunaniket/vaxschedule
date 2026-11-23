"""Start the VaxSchedule server: ``python run.py [--seed]``."""
import argparse
import os
from datetime import date, timedelta

from vaccination import create_app
from vaccination import scheduling
from vaccination.rules import parse_date

CENTRES = [
    ("PHC Banashankari", "Bengaluru Urban", "560085"),
    ("Govt Hospital Jayanagar", "Bengaluru Urban", "560041"),
    ("CHC Electronic City", "Bengaluru Urban", "560100"),
]
SLOTS = [("Covaxin", 40), ("Covishield", 60), ("Covaxin", 25)]


def seed(conn, today):
    """Add the demo centres and slots unless centres already exist."""
    if scheduling.list_centres(conn):
        return 0
    added = 0
    for name, district, pincode in CENTRES:
        centre = scheduling.add_centre(conn, name, district, pincode)
        for offset in range(4):
            day = today + timedelta(days=offset)
            for vaccine, capacity in SLOTS:
                scheduling.add_slot(conn, centre, day, vaccine, capacity)
                added += 1
    return added


def main(argv=None):
    """Parse arguments, optionally seed, and start the server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true",
                        help="add demo centres and slots")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "5000")))
    args = parser.parse_args(argv)

    app = create_app()
    if args.seed:
        fixed = app.config.get("TODAY")
        today = parse_date(fixed) if fixed else date.today()
        print(f"Seeded {seed(app.extensions['db'], today)} slots.")
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
