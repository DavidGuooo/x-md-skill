from __future__ import annotations

import re
from dataclasses import dataclass


POST_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:x|twitter)\.com/"
    r"(?:(?P<handle>[^/\s]+)/status|i/web/status)/(?P<id>\d+)"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)


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
