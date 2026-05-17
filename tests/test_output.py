import json
import tempfile
import unittest
from pathlib import Path

from youtube_to_wechat.output import write_outputs


class OutputTests(unittest.TestCase):
    def test_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = write_outputs(
                base_dir=Path(temp_dir),
                video_id="6C7FjGs22g8",
                meta={"video_id": "6C7FjGs22g8", "title": "Demo"},
                transcript="Transcript body",
                run={"status": "ok", "audio_path": "audio/demo.mp3"},
            )

            self.assertEqual(output_dir.name, "6C7FjGs22g8")
            self.assertEqual((output_dir / "transcript.txt").read_text(), "Transcript body\n")
            meta = json.loads((output_dir / "meta.json").read_text())
            self.assertEqual(meta["title"], "Demo")
            self.assertIn("Demo", (output_dir / "article.md").read_text())
            self.assertIn("<h1>Demo</h1>", (output_dir / "article.html").read_text())
            run = json.loads((output_dir / "run.json").read_text())
            self.assertEqual(run["audio_path"], "audio/demo.mp3")


if __name__ == "__main__":
    unittest.main()
