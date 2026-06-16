from __future__ import annotations

import argparse
from pathlib import Path

from .extractor import ExtractionError, extract_archive_posts
from .renderer import render_archive


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "archive":
        return archive_command(args)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m x_md")
    subparsers = parser.add_subparsers(dest="command")

    archive = subparsers.add_parser("archive", help="archive an X post to Markdown")
    archive.add_argument("url", help="X/Twitter post URL")
    archive.add_argument("--out", default="archives", help="output directory root")

    return parser


def archive_command(args: argparse.Namespace) -> int:
    output_root = Path(args.out)
    try:
        posts = extract_archive_posts(args.url)
        archive_dir = render_archive(args.url, posts, output_root)
    except (ExtractionError, ValueError) as error:
        print(f"x-md: {error}")
        return 2

    print(f"Wrote archive: {archive_dir}")
    return 0
