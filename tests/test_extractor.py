import unittest

from scripts.archive_x_post import parse_gallery_dl_json


class ExtractorTest(unittest.TestCase):
    def test_parse_gallery_dl_json_skips_log_prefix(self):
        stdout = '[cookies][info] Extracted cookies\n[\n  [2, {"tweet_id": 123}]\n]\n'

        self.assertEqual(parse_gallery_dl_json(stdout), [[2, {"tweet_id": 123}]])


if __name__ == "__main__":
    unittest.main()
