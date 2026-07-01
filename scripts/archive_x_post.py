#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
POST_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:x|twitter)\.com/"
    r"(?:(?P<handle>[^/\s]+)/status|i/web/status)/(?P<id>\d+)"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)


@dataclass
class Media:
    url: str | None = None
    alt_text: str | None = None
    source_path: Path | None = None
    relative_path: str | None = None


@dataclass
class Post:
    id: str
    text: str = ""
    author_id: str | None = None
    author_handle: str | None = None
    author_name: str | None = None
    created_at: str | None = None
    url: str | None = None
    parent_id: str | None = None
    quoted_id: str | None = None
    media: list[Media] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def author_key(self) -> str:
        if self.author_id:
            return f"id:{self.author_id}"
        if self.author_handle:
            return f"handle:{self.author_handle.lower()}"
        return "unknown"

    @property
    def display_author(self) -> str:
        if self.author_name and self.author_handle:
            return f"{self.author_name} @{self.author_handle}"
        if self.author_name:
            return self.author_name
        if self.author_handle:
            return f"@{self.author_handle}"
        return "unknown author"


@dataclass(frozen=True)
class ParsedPostUrl:
    post_id: str
    handle: str | None

    @property
    def canonical_url(self) -> str:
        handle = self.handle or "i/web"
        if handle == "i/web":
            return f"https://x.com/i/web/status/{self.post_id}"
        return f"https://x.com/{handle}/status/{self.post_id}"


class ExtractionError(RuntimeError):
    pass


class GalleryDlExtractor:
    def extract(self, url: str) -> dict[str, Post]:
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
            return normalize_posts(raw_posts, copied_media)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/archive_x_post.py")
    subparsers = parser.add_subparsers(dest="command")
    archive = subparsers.add_parser("archive", help="archive an X post to Markdown")
    archive.add_argument("url", help="X/Twitter post URL")
    archive.add_argument("--out", default="archives", help="output directory root")
    args = parser.parse_args(argv)

    if args.command != "archive":
        parser.print_help()
        return 1

    try:
        posts = extract_archive_posts(args.url)
        note_path = render_archive(args.url, posts, Path(args.out))
    except (ExtractionError, ValueError) as error:
        print(f"x-md: {error}")
        return 2

    print(f"Wrote archive: {note_path}")
    return 0


def parse_post_url(url: str) -> ParsedPostUrl:
    match = POST_URL_RE.match(url.strip())
    if not match:
        raise ValueError(
            "Expected an X/Twitter post URL like "
            "https://x.com/user/status/123 or https://twitter.com/i/web/status/123"
        )
    handle = match.group("handle")
    if handle and handle.lower() == "i":
        handle = None
    return ParsedPostUrl(post_id=match.group("id"), handle=handle)


def post_url(post_id: str, handle: str | None = None) -> str:
    if handle:
        return f"https://x.com/{handle}/status/{post_id}"
    return f"https://x.com/i/web/status/{post_id}"


def extract_archive_posts(url: str, extractor: GalleryDlExtractor | None = None) -> dict[str, Post]:
    parsed = parse_post_url(url)
    extractor = extractor or GalleryDlExtractor()
    all_posts = extractor.extract(parsed.canonical_url)

    current_id = parsed.post_id
    seen_quote_ids: set[str] = set()
    while True:
        current = all_posts.get(current_id)
        if not current or not current.quoted_id or current.quoted_id in seen_quote_ids:
            break
        seen_quote_ids.add(current.quoted_id)
        if current.quoted_id not in all_posts:
            all_posts.update(extractor.extract(post_url(current.quoted_id)))
        current_id = current.quoted_id

    return all_posts


def gallery_dl_config(scratch: Path) -> dict[str, Any]:
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


def dump_metadata(config_path: Path, scratch: Path, url: str) -> list[dict[str, Any]]:
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
    posts: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, list) and len(item) >= 2 and item[0] == 2 and isinstance(item[1], dict):
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


def parse_gallery_dl_json(stdout: str) -> list[Any]:
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


def normalize_posts(raw_posts: list[dict[str, Any]], media_files: list[Path]) -> dict[str, Post]:
    posts: dict[str, Post] = {}
    for raw in flatten_raw_posts(raw_posts):
        post = normalize_post(raw)
        if post:
            posts[post.id] = post

    link_gallery_dl_quoted_posts(posts)
    attach_downloaded_media(posts, media_files)
    return posts


def flatten_raw_posts(raw_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    seen: set[int] = set()

    def visit(raw: dict[str, Any]) -> None:
        marker = id(raw)
        if marker in seen:
            return
        seen.add(marker)
        flattened.append(raw)
        for key in ("quoted", "quote", "quoted_status", "quoted_tweet"):
            value = raw.get(key)
            if isinstance(value, dict):
                visit(value)

    for raw in raw_posts:
        visit(raw)
    return flattened


def link_gallery_dl_quoted_posts(posts: dict[str, Post]) -> None:
    for quoted_post in list(posts.values()):
        quoting_id = normalize_id(quoted_post.raw.get("quote_id"))
        if not quoting_id or quoting_id == quoted_post.id:
            continue
        quoting_post = posts.get(quoting_id)
        if quoting_post and not quoting_post.quoted_id:
            quoting_post.quoted_id = quoted_post.id


def normalize_post(raw: dict[str, Any]) -> Post | None:
    post_id = first_string(raw, "tweet_id", "id", "rest_id", "status_id", "conversation_id")
    if not post_id:
        return None

    author = first_mapping(raw, "author", "core.user_results.result", "legacy.user")
    user = first_mapping(raw, "user")
    legacy = first_mapping(raw, "legacy", "status")
    text = first_string(raw, "content", "text", "full_text", "description")
    if not text and legacy:
        text = first_string(legacy, "full_text", "text")

    author_handle = first_string(raw, "screen_name", "username")
    author_id = first_string(raw, "user_id", "author_id")
    author_name = first_string(raw, "name")
    if author:
        author_handle = first_string(author, "screen_name", "username", "handle", "name") or author_handle
        author_id = first_string(author, "id", "rest_id", "user_id") or author_id
        author_name = first_string(author, "nick", "display_name", "name") or author_name
    elif user:
        author_handle = author_handle or first_string(user, "screen_name", "username", "handle", "name")
        author_id = author_id or first_string(user, "id", "rest_id", "user_id")
        author_name = author_name or first_string(user, "nick", "display_name", "name")

    parent_id = normalize_id(
        first_value(
            raw,
            "reply_id",
            "reply_to_id",
            "in_reply_to_status_id",
            "in_reply_to_status_id_str",
            "legacy.in_reply_to_status_id_str",
            "reply_to",
        )
    )
    quoted_id = normalize_id(
        first_value(
            raw,
            "quoted_id",
            "quoted_status_id",
            "quoted_status_id_str",
            "legacy.quoted_status_id_str",
            "quoted.id",
            "quoted.tweet_id",
            "quoted.rest_id",
        )
    )

    created_at = first_string(raw, "date", "created_at", "legacy.created_at")
    url = first_string(raw, "url", "tweet_url", "web_url") or post_url(post_id, author_handle)

    return Post(
        id=post_id,
        text=text or "",
        author_id=author_id,
        author_handle=author_handle,
        author_name=author_name,
        created_at=created_at,
        url=url,
        parent_id=parent_id,
        quoted_id=quoted_id,
        media=normalize_inline_media(raw),
        raw=raw,
    )


def normalize_inline_media(raw: dict[str, Any]) -> list[Media]:
    media_items: list[Media] = []
    candidates: list[dict[str, Any]] = []
    for key in ("media", "photos", "images", "attachments"):
        value = raw.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            candidates.extend(item for item in value.values() if isinstance(item, dict))

    for item in candidates:
        media_type = str(item.get("type") or item.get("media_type") or "photo").lower()
        if media_type not in {"photo", "image", "animated_gif"}:
            continue
        media_items.append(
            Media(
                url=first_string(item, "url", "media_url_https", "media_url", "expanded_url"),
                alt_text=first_string(item, "alt_text", "ext_alt_text", "description"),
            )
        )
    return media_items


def attach_downloaded_media(posts: dict[str, Post], media_files: list[Path]) -> None:
    for media_file in media_files:
        if media_file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        post_id = media_file.name.split("_", 1)[0].split("-", 1)[0]
        post = posts.get(post_id)
        if post and not any(item.source_path == media_file for item in post.media):
            post.media.append(Media(source_path=media_file))


def first_string(mapping: dict[str, Any], *keys: str) -> str | None:
    value = first_value(mapping, *keys)
    normalized = normalize_id(value)
    if normalized is not None:
        return normalized
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def first_mapping(mapping: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = nested_get(mapping, key)
        if isinstance(value, dict):
            return value
    return None


def first_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = nested_get(mapping, key)
        if value not in (None, ""):
            return value
    return None


def nested_get(mapping: dict[str, Any], dotted_key: str) -> Any:
    value: Any = mapping
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value) if value else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return stripped if int(stripped) else None
        return None
    if isinstance(value, dict):
        return first_string(value, "id", "tweet_id", "rest_id", "status_id")
    return None


def render_archive(url: str, posts: dict[str, Post], output_root: Path) -> Path:
    parsed = parse_post_url(url)
    input_post = posts.get(parsed.post_id)
    if not input_post:
        raise ValueError(f"Could not find input post {parsed.post_id} in extracted data")

    assets_dir = output_root / "raw" / "assets"
    ensure_assets_dir(assets_dir)

    quoted_posts = quote_chain(posts, input_post.id)
    continuation_posts = self_thread_continuation(posts, input_post.id, input_post.author_key)
    main_chain_ids = {input_post.id, *(post.id for post in continuation_posts)}
    reply_paths = kept_reply_paths(posts, input_post.id, input_post.author_key, main_chain_ids)

    selected_posts = {input_post.id: input_post}
    for post in quoted_posts:
        selected_posts[post.id] = post
    for post in continuation_posts:
        selected_posts[post.id] = post
    for path in reply_paths:
        for post in path:
            selected_posts[post.id] = post

    materialize_assets(selected_posts, assets_dir)
    markdown = build_markdown(parsed.canonical_url, input_post, quoted_posts, continuation_posts, reply_paths)
    note_path = output_root / f"{archive_slug(input_post)}.md"
    note_path.write_text(markdown, encoding="utf-8")
    return note_path


def build_markdown(
    source_url: str,
    input_post: Post,
    quoted_posts: list[Post],
    continuation_posts: list[Post],
    reply_paths: list[list[Post]],
) -> str:
    lines = [
        "---",
        f'source: "{source_url}"',
        "author:",
        f'  - "{escape_yaml(frontmatter_author(input_post))}"',
        f"published: {iso_date(input_post.created_at) or ''}",
        f"created: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "---",
        "",
        "# X Archive",
        "",
        "## Post",
        "",
        render_post(input_post),
    ]
    for post in continuation_posts:
        lines.extend(["", render_post(post)])

    if quoted_posts:
        lines.extend(["", "## Quoted Posts", ""])
        for index, post in enumerate(quoted_posts, start=1):
            lines.extend([f"### Quote {index}", "", render_post(post), ""])

    if reply_paths:
        lines.extend(["", "## Replies", ""])
        for index, path in enumerate(reply_paths, start=1):
            lines.extend([f"### Reply Path {index}", ""])
            for post in path:
                lines.extend([render_post(post), ""])

    return "\n".join(lines).rstrip() + "\n"


def quote_chain(posts: dict[str, Post], root_id: str) -> list[Post]:
    chain: list[Post] = []
    seen: set[str] = set()
    current = posts.get(root_id)
    while current and current.quoted_id and current.quoted_id not in seen:
        seen.add(current.id)
        quoted = posts.get(current.quoted_id)
        if not quoted:
            break
        chain.append(quoted)
        current = quoted
    return chain


def self_thread_continuation(posts: dict[str, Post], root_id: str, author_key: str) -> list[Post]:
    """Walk unambiguous same-author direct-reply chains off the root.

    On X, posting long text as a thread means each reply directly replies to
    the author's own previous post. Those are a continuation of the original
    post, not a separate branch, so they get merged into it instead of being
    listed as their own "Reply Path".
    """
    children_by_parent: dict[str, list[Post]] = {}
    for post in posts.values():
        if post.parent_id:
            children_by_parent.setdefault(post.parent_id, []).append(post)

    chain: list[Post] = []
    seen = {root_id}
    current_id = root_id
    while True:
        candidates = [
            child
            for child in children_by_parent.get(current_id, [])
            if child.author_key == author_key and child.id not in seen
        ]
        if len(candidates) != 1:
            break
        next_post = candidates[0]
        chain.append(next_post)
        seen.add(next_post.id)
        current_id = next_post.id
    return chain


def kept_reply_paths(
    posts: dict[str, Post],
    root_id: str,
    input_author_key: str,
    main_chain_ids: set[str],
) -> list[list[Post]]:
    paths: list[list[Post]] = []
    seen_paths: set[tuple[str, ...]] = set()
    for post in sorted(posts.values(), key=lambda item: (item.created_at or "", item.id)):
        if post.id in main_chain_ids or post.author_key != input_author_key:
            continue
        path = path_from_root(posts, root_id, post.id)
        trimmed = trim_main_chain(path, main_chain_ids)
        key = tuple(item.id for item in trimmed)
        if trimmed and key not in seen_paths:
            seen_paths.add(key)
            paths.append(trimmed)
    return drop_prefix_paths(paths)


def trim_main_chain(path: list[Post], main_chain_ids: set[str]) -> list[Post]:
    index = 0
    while index < len(path) and path[index].id in main_chain_ids:
        index += 1
    return path[index:]


def drop_prefix_paths(paths: list[list[Post]]) -> list[list[Post]]:
    id_sequences = [tuple(post.id for post in path) for path in paths]
    kept: list[list[Post]] = []
    for path, seq in zip(paths, id_sequences):
        if any(
            seq != other and len(seq) < len(other) and other[: len(seq)] == seq
            for other in id_sequences
        ):
            continue
        kept.append(path)
    return kept


def path_from_root(posts: dict[str, Post], root_id: str, target_id: str) -> list[Post]:
    path: list[Post] = []
    seen: set[str] = set()
    current_id: str | None = target_id
    while current_id and current_id not in seen:
        seen.add(current_id)
        post = posts.get(current_id)
        if not post:
            return []
        path.append(post)
        if current_id == root_id:
            return list(reversed(path))
        current_id = post.parent_id
    return []


def render_post(post: Post) -> str:
    lines = [f"[{post.created_at or 'unknown time'}] {post.display_author}"]
    if post.text:
        lines.extend(["", post.text.strip()])
    for media in post.media:
        if media.relative_path:
            alt = media.alt_text or f"image from post {post.id}"
            lines.extend(["", f"![{escape_markdown_alt(alt)}]({media.relative_path})"])
    return "\n".join(lines)


def ensure_assets_dir(assets_dir: Path) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)


def materialize_assets(posts: dict[str, Post], assets_dir: Path) -> None:
    for post in posts.values():
        image_index = 1
        for media in post.media:
            if not media.source_path or not media.source_path.exists():
                continue
            extension = media.source_path.suffix.lower() or ".jpg"
            target = assets_dir / f"{post.id}-{image_index}{extension}"
            image_index += 1
            shutil.copy2(media.source_path, target)
            media.relative_path = f"raw/assets/{target.name}"


def archive_slug(post: Post) -> str:
    date = compact_date(post.created_at) or "undated"
    handle = sanitize_slug(post.author_handle or post.author_name or "unknown")
    return f"{date}-{handle}-{post.id}"


def compact_date(value: str | None) -> str | None:
    date = iso_date(value)
    return date.replace("-", "") if date else None


def iso_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", value)
    return "-".join(match.groups()) if match else None


def frontmatter_author(post: Post) -> str:
    if post.author_handle:
        return f"@{post.author_handle}"
    if post.author_name:
        return post.author_name
    return "unknown"


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip("@ ").lower()).strip("-")
    return slug or "unknown"


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def escape_markdown_alt(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")


if __name__ == "__main__":
    raise SystemExit(main())
