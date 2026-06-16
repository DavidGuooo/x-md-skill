from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .models import Media, Post
from .threading import kept_reply_paths, quote_chain
from .url import parse_post_url


def render_archive(url: str, posts: dict[str, Post], output_root: Path) -> Path:
    parsed = parse_post_url(url)
    input_post = posts.get(parsed.post_id)
    if not input_post:
        raise ValueError(f"Could not find input post {parsed.post_id} in extracted data")

    archive_dir = output_root / archive_slug(input_post)
    assets_dir = archive_dir / "assets"
    reset_assets_dir(assets_dir)

    quoted_posts = quote_chain(posts, input_post.id)
    reply_paths = kept_reply_paths(posts, input_post.id, input_post.author_key)
    selected_posts = selected_archive_posts(input_post, quoted_posts, reply_paths)
    materialize_assets(selected_posts, assets_dir)

    markdown = build_markdown(
        source_url=parsed.canonical_url,
        input_post=input_post,
        quoted_posts=quoted_posts,
        reply_paths=reply_paths,
    )
    index_path = archive_dir / "index.md"
    index_path.write_text(markdown, encoding="utf-8")
    return archive_dir


def reset_assets_dir(assets_dir: Path) -> None:
    if assets_dir.exists():
        for path in assets_dir.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    assets_dir.mkdir(parents=True, exist_ok=True)


def selected_archive_posts(
    input_post: Post,
    quoted_posts: list[Post],
    reply_paths: list[list[Post]],
) -> dict[str, Post]:
    selected = {input_post.id: input_post}
    for post in quoted_posts:
        selected[post.id] = post
    for path in reply_paths:
        for post in path:
            selected[post.id] = post
    return selected


def build_markdown(
    source_url: str,
    input_post: Post,
    quoted_posts: list[Post],
    reply_paths: list[list[Post]],
) -> str:
    lines = [
        "---",
        f'source_url: "{source_url}"',
        f'post_id: "{input_post.id}"',
        f'author: "{escape_yaml(input_post.display_author)}"',
        f'created_at: "{escape_yaml(input_post.created_at or "")}"',
        f'archived_at: "{datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}"',
        "---",
        "",
        "# X Archieve",
        "",
        "## Post",
        "",
        render_post(input_post),
    ]

    if quoted_posts:
        lines.extend(["", "## Quoted Posts", ""])
        for index, post in enumerate(quoted_posts, start=1):
            lines.extend([f"### Quote {index}", "", render_post(post), ""])

    if reply_paths:
        lines.extend(["", "## Replies", ""])
        for index, path in enumerate(reply_paths, start=1):
            lines.extend([f"### Reply Path {index}", ""])
            visible_path = path[1:] if path and path[0].id == input_post.id else path
            for post in visible_path:
                lines.append(render_post(post))
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_post(post: Post) -> str:
    lines = [
        f"[{post.created_at or 'unknown time'}] {post.display_author}",
    ]
    if post.text:
        lines.extend(["", post.text.strip()])
    for media in post.media:
        if not media.relative_path:
            continue
        alt = media.alt_text or f"image from post {post.id}"
        lines.extend(["", f"![{escape_markdown_alt(alt)}]({media.relative_path})"])
    return "\n".join(lines)


def materialize_assets(posts: dict[str, Post], assets_dir: Path) -> None:
    for post in posts.values():
        image_index = 1
        for media in post.media:
            if not media.source_path or not media.source_path.exists():
                continue
            extension = media.source_path.suffix.lower() or ".jpg"
            filename = f"{post.id}-{image_index}{extension}"
            image_index += 1
            target = assets_dir / filename
            shutil.copy2(media.source_path, target)
            media.relative_path = f"assets/{filename}"


def archive_slug(post: Post) -> str:
    date = compact_date(post.created_at) or "undated"
    handle = sanitize_slug(post.author_handle or post.author_name or "unknown")
    return f"{date}-{handle}-{post.id}"


def compact_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", value)
    if match:
        return "".join(match.groups())
    return None


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip("@ ").lower()).strip("-")
    return slug or "unknown"


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def escape_markdown_alt(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")
