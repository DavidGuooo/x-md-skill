import tempfile
import unittest
from pathlib import Path

from scripts.archive_x_post import normalize_posts


class NormalizeTest(unittest.TestCase):
    def test_flattens_nested_quoted_post(self):
        posts = normalize_posts(
            [
                {
                    "id": "1",
                    "content": "A",
                    "user": {"id": "p", "screen_name": "poster"},
                    "quoted": {
                        "id": "2",
                        "content": "B",
                        "user": {"id": "q", "screen_name": "quoted"},
                    },
                }
            ],
            [],
        )

        self.assertEqual(posts["1"].quoted_id, "2")
        self.assertEqual(posts["2"].text, "B")
        self.assertEqual(posts["2"].author_handle, "quoted")

    def test_attaches_downloaded_image_by_filename_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "123_1.jpg"
            path.write_bytes(b"image")

            posts = normalize_posts([{"id": "123", "content": "hello"}], [path])

        self.assertEqual(len(posts["123"].media), 1)
        self.assertEqual(posts["123"].media[0].source_path.name, "123_1.jpg")

    def test_normalizes_gallery_dl_twitter_author_fields(self):
        posts = normalize_posts(
            [
                {
                    "tweet_id": 123,
                    "content": "hello",
                    "quote_id": 0,
                    "reply_id": 0,
                    "user": {"id": 456, "name": "handle", "nick": "Display Name"},
                }
            ],
            [],
        )

        self.assertEqual(posts["123"].author_id, "456")
        self.assertEqual(posts["123"].author_handle, "handle")
        self.assertEqual(posts["123"].author_name, "Display Name")
        self.assertIsNone(posts["123"].quoted_id)
        self.assertIsNone(posts["123"].parent_id)

    def test_prefers_gallery_dl_author_over_root_user_for_replies(self):
        posts = normalize_posts(
            [
                {
                    "tweet_id": 123,
                    "content": "reply",
                    "reply_to": "aleabitoreddit",
                    "reply_id": 100,
                    "author": {"id": 999, "name": "actual_reply_author", "nick": "Actual Reply Author"},
                    "user": {"id": 456, "name": "aleabitoreddit", "nick": "Serenity"},
                }
            ],
            [],
        )

        self.assertEqual(posts["123"].author_id, "999")
        self.assertEqual(posts["123"].author_handle, "actual_reply_author")
        self.assertEqual(posts["123"].author_name, "Actual Reply Author")
        self.assertEqual(posts["123"].parent_id, "100")

    def test_links_gallery_dl_quoted_post_back_to_quoting_post(self):
        posts = normalize_posts(
            [
                {
                    "tweet_id": 10,
                    "content": "quoting post",
                    "quote_id": 0,
                    "user": {"id": 1, "name": "poster", "nick": "Poster"},
                },
                {
                    "tweet_id": 9,
                    "content": "quoted post",
                    "quote_id": 10,
                    "user": {"id": 1, "name": "poster", "nick": "Poster"},
                },
                {
                    "tweet_id": 8,
                    "content": "earlier quoted post",
                    "quote_id": 9,
                    "user": {"id": 1, "name": "poster", "nick": "Poster"},
                },
            ],
            [],
        )

        self.assertEqual(posts["10"].quoted_id, "9")
        self.assertEqual(posts["9"].quoted_id, "8")


if __name__ == "__main__":
    unittest.main()
