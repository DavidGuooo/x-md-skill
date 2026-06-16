from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .models import ExtractionResult, Post
from .normalize import IMAGE_EXTENSIONS, normalize_posts
from .url import parse_post_url, post_url


class ExtractionError(RuntimeError):
    pass


class GalleryDlExtractor:
    def extract(self, url: str) -> ExtractionResult:
        with tempfile.TemporaryDirectory(prefix="x-md-") as tmp:
            scratch = Path(tmp)
            config_path = scratch / "gallery-dl.json"
            media_dir = scratch / "media"
            config_path.write_text(json.dumps(gallery_dl_config(scratch), indent=2), encoding="utf-8")

            raw_posts = dump_metadata(config_path, scratch, url)
            download_media(config_path, scratch, url)

            media_files = [
                path
                for path in media_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ]
            copied_media = copy_to_stable_temp(media_files)
            posts = normalize_posts(raw_posts, copied_media)
            return ExtractionResult(posts=posts, media_files=copied_media)


def extract_archive_posts(url: str, extractor: GalleryDlExtractor | None = None) -> dict[str, Post]:
    parsed = parse_post_url(url)
    extractor = extractor or GalleryDlExtractor()
    all_posts: dict[str, Post] = {}

    result = extractor.extract(parsed.canonical_url)
    all_posts.update(result.posts)

    current_id = parsed.post_id
    seen_quote_ids: set[str] = set()
    while True:
        current = all_posts.get(current_id)
        if not current or not current.quoted_id or current.quoted_id in seen_quote_ids:
            break
        seen_quote_ids.add(current.quoted_id)
        if current.quoted_id not in all_posts:
            quoted_result = extractor.extract(post_url(current.quoted_id))
            all_posts.update(quoted_result.posts)
        current_id = current.quoted_id

    return all_posts


def gallery_dl_config(scratch: Path) -> dict:
    return {
        "extractor": {
            "base-directory": str(scratch),
            "directory": ["media"],
            "filename": "{tweet_id}_{num}.{extension}",
            "cookies": ["chrome"],
            "twitter": {
                "browser": "chrome:macos",
                "cards": False,
                "conversations": True,
                "quoted": True,
                "replies": True,
                "retweets": False,
                "text-tweets": True,
                "videos": False,
            },
        }
    }


def dump_metadata(config_path: Path, scratch: Path, url: str) -> list[dict]:
    command = [
        sys.executable,
        "-m",
        "gallery_dl",
        "--config-json",
        str(config_path),
        "-j",
        url,
    ]
    completed = subprocess.run(command, cwd=scratch, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ExtractionError(f"gallery-dl metadata extraction failed for {url}\n{detail}")

    payload = parse_gallery_dl_json(completed.stdout)
    posts: list[dict] = []
    for item in payload:
        if not isinstance(item, list) or len(item) < 2:
            continue
        message_type = item[0]
        if message_type == 2 and isinstance(item[1], dict):
            posts.append(item[1])
    return posts


def download_media(config_path: Path, scratch: Path, url: str) -> None:
    command = [
        sys.executable,
        "-m",
        "gallery_dl",
        "--config-json",
        str(config_path),
        url,
    ]
    completed = subprocess.run(command, cwd=scratch, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ExtractionError(f"gallery-dl media download failed for {url}\n{detail}")


def parse_gallery_dl_json(stdout: str) -> list:
    start = stdout.find("[\n")
    if start == -1:
        start = stdout.find("[[")
    if start == -1:
        raise ExtractionError("gallery-dl did not return JSON metadata")
    try:
        payload = json.loads(stdout[start:])
    except json.JSONDecodeError as error:
        raise ExtractionError(f"gallery-dl returned invalid JSON metadata: {error}") from error
    if not isinstance(payload, list):
        raise ExtractionError("gallery-dl JSON metadata was not a list")
    return payload


def copy_to_stable_temp(paths: list[Path]) -> list[Path]:
    stable = Path(tempfile.mkdtemp(prefix="x-md-media-"))
    copied: list[Path] = []
    for path in paths:
        target = stable / path.name
        target.write_bytes(path.read_bytes())
        copied.append(target)
    return copied
