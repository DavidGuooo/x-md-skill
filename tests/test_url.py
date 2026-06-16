import unittest

from x_md.url import parse_post_url


class ParsePostUrlTest(unittest.TestCase):
    def test_x_status_url(self):
        parsed = parse_post_url("https://x.com/example/status/1234567890")

        self.assertEqual(parsed.post_id, "1234567890")
        self.assertEqual(parsed.handle, "example")
        self.assertEqual(parsed.canonical_url, "https://x.com/example/status/1234567890")

    def test_twitter_status_url_with_query(self):
        parsed = parse_post_url("https://twitter.com/example/status/1234567890?s=20")

        self.assertEqual(parsed.post_id, "1234567890")
        self.assertEqual(parsed.handle, "example")

    def test_web_status_url(self):
        parsed = parse_post_url("https://twitter.com/i/web/status/1234567890")

        self.assertEqual(parsed.post_id, "1234567890")
        self.assertIsNone(parsed.handle)
        self.assertEqual(parsed.canonical_url, "https://x.com/i/web/status/1234567890")

    def test_rejects_non_post_url(self):
        with self.assertRaises(ValueError):
            parse_post_url("https://x.com/example")


if __name__ == "__main__":
    unittest.main()
