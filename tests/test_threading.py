import unittest

from scripts.archive_x_post import Post, kept_reply_paths, quote_chain


class ThreadingTest(unittest.TestCase):
    def test_keeps_ancestor_path_through_input_author_reply(self):
        posts = {
            "root": Post(id="root", author_id="p", text="input"),
            "a": Post(id="a", author_id="a", parent_id="root"),
            "b": Post(id="b", author_id="b", parent_id="a"),
            "c": Post(id="c", author_id="c", parent_id="b"),
            "p": Post(id="p", author_id="p", parent_id="c"),
            "d": Post(id="d", author_id="d", parent_id="p"),
        }

        paths = kept_reply_paths(posts, "root", posts["root"].author_key)

        self.assertEqual([[post.id for post in path] for path in paths], [["root", "a", "b", "c", "p"]])

    def test_ignores_input_author_reply_outside_input_post_descendants(self):
        posts = {
            "root": Post(id="root", author_id="p"),
            "other-root": Post(id="other-root", author_id="x"),
            "p": Post(id="p", author_id="p", parent_id="other-root"),
        }

        self.assertEqual(kept_reply_paths(posts, "root", posts["root"].author_key), [])

    def test_quote_chain_stops_on_cycle(self):
        posts = {
            "a": Post(id="a", quoted_id="b"),
            "b": Post(id="b", quoted_id="c"),
            "c": Post(id="c", quoted_id="b"),
        }

        self.assertEqual([post.id for post in quote_chain(posts, "a")], ["b", "c"])


if __name__ == "__main__":
    unittest.main()
