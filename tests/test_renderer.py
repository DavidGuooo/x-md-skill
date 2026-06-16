import tempfile
import unittest
from pathlib import Path

from x_md.models import Media, Post
from x_md.renderer import build_markdown, render_archive


class RendererTest(unittest.TestCase):
    def test_build_markdown_uses_front_matter_and_local_images(self):
        post = Post(
            id="123",
            text="hello",
            author_handle="poster",
            created_at="2026-05-29T12:00:00Z",
            url="https://x.com/poster/status/123",
            media=[Media(relative_path="assets/123-1.jpg", alt_text="alt")],
        )

        markdown = build_markdown("https://x.com/poster/status/123", post, [], [])

        self.assertIn('source_url: "https://x.com/poster/status/123"', markdown)
        self.assertIn("# X Archieve", markdown)
        self.assertIn("## Post", markdown)
        self.assertIn("[2026-05-29T12:00:00Z] @poster", markdown)
        self.assertNotIn("[Source]", markdown)
        self.assertIn("![alt](assets/123-1.jpg)", markdown)

    def test_build_markdown_uses_display_name_and_handle(self):
        post = Post(id="123", text="hello", author_handle="aleabitoreddit", author_name="Serenity")

        markdown = build_markdown("https://x.com/aleabitoreddit/status/123", post, [], [])

        self.assertIn('author: "Serenity @aleabitoreddit"', markdown)
        self.assertIn("[unknown time] Serenity @aleabitoreddit", markdown)

    def test_build_markdown_uses_new_reply_headers_without_indentation(self):
        root = Post(id="1", text="root", author_id="p", author_handle="poster", author_name="Poster", created_at="2026-05-29 12:00:00")
        reply = Post(id="2", text="reply", author_handle="replyer", author_name="Replyer", created_at="2026-05-29 12:01:00")

        markdown = build_markdown("https://x.com/poster/status/1", root, [], [[root, reply]])

        self.assertIn("## Replies", markdown)
        self.assertIn("### Reply Path 1", markdown)
        self.assertEqual(markdown.count("[2026-05-29 12:00:00] Poster @poster"), 1)
        self.assertIn("[2026-05-29 12:01:00] Replyer @replyer", markdown)
        self.assertNotIn("\n  [2026-05-29 12:01:00]", markdown)

    def test_render_archive_writes_index_and_assets_without_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            source.write_bytes(b"image")
            posts = {
                "123": Post(
                    id="123",
                    text="hello",
                    author_handle="poster",
                    created_at="2026-05-29T12:00:00Z",
                    media=[Media(source_path=source)],
                )
            }

            archive_dir = render_archive("https://x.com/poster/status/123", posts, root / "archives")

            self.assertTrue((archive_dir / "index.md").exists())
            self.assertTrue((archive_dir / "assets" / "123-1.jpg").exists())
            self.assertEqual(list(archive_dir.glob("*.json")), [])

    def test_render_archive_does_not_copy_filtered_conversation_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kept = root / "kept.jpg"
            filtered = root / "filtered.jpg"
            kept.write_bytes(b"kept")
            filtered.write_bytes(b"filtered")
            posts = {
                "123": Post(
                    id="123",
                    author_id="p",
                    author_handle="poster",
                    created_at="2026-05-29T12:00:00Z",
                    media=[Media(source_path=kept)],
                ),
                "456": Post(
                    id="456",
                    author_id="someone-else",
                    parent_id="123",
                    media=[Media(source_path=filtered)],
                ),
            }

            archive_dir = render_archive("https://x.com/poster/status/123", posts, root / "archives")

            self.assertTrue((archive_dir / "assets" / "123-1.jpg").exists())
            self.assertFalse((archive_dir / "assets" / "456-1.jpg").exists())


if __name__ == "__main__":
    unittest.main()
