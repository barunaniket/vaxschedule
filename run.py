"""Start the VaxSchedule server: ``python run.py [--seed]``."""
import argparse
import os

from vaccination import create_app


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
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
