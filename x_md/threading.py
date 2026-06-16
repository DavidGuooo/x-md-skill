from __future__ import annotations

from .models import Post


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


def kept_reply_paths(posts: dict[str, Post], root_id: str, input_author_key: str) -> list[list[Post]]:
    paths: list[list[Post]] = []
    seen_paths: set[tuple[str, ...]] = set()

    for post in sorted(posts.values(), key=sort_key):
        if post.id == root_id or post.author_key != input_author_key:
            continue
        path = path_from_root(posts, root_id, post.id)
        if not path:
            continue
        key = tuple(item.id for item in path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        paths.append(path)

    return paths


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


def sort_key(post: Post) -> tuple[str, str]:
    return (post.created_at or "", post.id)
