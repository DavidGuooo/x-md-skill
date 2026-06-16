#!/usr/bin/env python3
"""Wrapper entrypoint for the bundled x-md CLI."""

from x_md.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
