import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from update_cards import update_cards, validate_svg


STATS = b'<svg xmlns="http://www.w3.org/2000/svg"><text data-testid="commits">42</text><text data-testid="prs">7</text><text data-testid="issues">3</text></svg>'
LANGUAGES = b'<svg xmlns="http://www.w3.org/2000/svg"><text data-testid="lang-name">Python 100%</text></svg>'
ERROR = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Resource not accessible by integration</text></svg>'


class UpdateCardsTest(unittest.TestCase):
    @patch("update_cards.urlopen")
    def test_publishes_valid_snapshots(self, open_url):
        open_url.side_effect = [io.BytesIO(STATS), io.BytesIO(LANGUAGES)]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            update_cards("alyldas", directory)
            self.assertEqual(STATS, (directory / "stats.svg").read_bytes())
            self.assertEqual(LANGUAGES, (directory / "top-langs.svg").read_bytes())
            self.assertEqual(2, len(list(directory.iterdir())))

    @patch("update_cards.time.sleep")
    @patch("update_cards.urlopen")
    def test_error_response_preserves_both_previous_snapshots(self, open_url, sleep):
        open_url.side_effect = [io.BytesIO(STATS)] + [io.BytesIO(ERROR) for _ in range(3)]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for filename in ("stats.svg", "top-langs.svg"):
                (directory / filename).write_bytes(b"last good snapshot")
            with self.assertRaises(ValueError):
                update_cards("alyldas", directory)
            for filename in ("stats.svg", "top-langs.svg"):
                self.assertEqual(b"last good snapshot", (directory / filename).read_bytes())
            self.assertEqual(4, open_url.call_count)

    def test_rejects_html_and_active_svg(self):
        for data in (
            b"<html>Upstream unavailable</html>",
            LANGUAGES.replace(b"</svg>", b"<script>alert(1)</script></svg>"),
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_svg(data, {"lang-name"})


if __name__ == "__main__":
    unittest.main()
