from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Media, Post
from .url import post_url

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_posts(raw_posts: list[dict[str, Any]], media_files: list[Path]) -> dict[str, Post]:
    posts: dict[str, Post] = {}
    for raw in flatten_raw_posts(raw_posts):
        post = normalize_post(raw)
        if not post:
            continue
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
    post_id = first_string(
        raw,
        "tweet_id",
        "id",
        "rest_id",
        "status_id",
        "conversation_id",
    )
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
    media = normalize_inline_media(raw)

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
        media=media,
        raw=raw,
    )


def normalize_inline_media(raw: dict[str, Any]) -> list[Media]:
    media_items: list[Media] = []
    candidates = []
    for key in ("media", "photos", "images", "attachments"):
        value = raw.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, dict):
            candidates.extend(value.values())

    for item in candidates:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("type") or item.get("media_type") or "photo").lower()
        if media_type not in {"photo", "image", "animated_gif"}:
            continue
        url = first_string(item, "url", "media_url_https", "media_url", "expanded_url")
        alt = first_string(item, "alt_text", "ext_alt_text", "description")
        media_items.append(Media(url=url, alt_text=alt))
    return media_items


def attach_downloaded_media(posts: dict[str, Post], media_files: list[Path]) -> None:
    for media_file in media_files:
        if media_file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        post_id = media_file.name.split("_", 1)[0].split("-", 1)[0]
        post = posts.get(post_id)
        if not post:
            continue
        existing = next((item for item in post.media if item.source_path == media_file), None)
        if existing:
            continue
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
        if value is not None and value != "":
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
