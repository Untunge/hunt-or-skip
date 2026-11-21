"""Allow `python -m hunt_or_skip`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
