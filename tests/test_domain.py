import unittest

from youtube_to_wechat.domain import (
    CompareEvaluation,
    SourceMetadata,
    TranscriptArtifact,
    WriterProfile,
)


class DomainNamingTests(unittest.TestCase):
    def test_source_metadata_uses_source_neutral_names(self):
        source = SourceMetadata(
            source_type="youtube",
            source_id="6C7FjGs22g8",
            source_url="https://www.youtube.com/watch?v=6C7FjGs22g8",
            title="Demo",
            author="Channel",
        )

        self.assertEqual(source.source_type, "youtube")
        self.assertEqual(source.source_id, "6C7FjGs22g8")
        self.assertEqual(source.author, "Channel")

    def test_transcript_artifact_names_text_origin(self):
        transcript = TranscriptArtifact(
            text="hello world",
            origin="caption",
            language="en",
            source_path="outputs/youtube/demo/_subs/demo.en.vtt",
        )

        self.assertEqual(transcript.origin, "caption")
        self.assertEqual(transcript.language, "en")
        self.assertIn("_subs", transcript.source_path)

    def test_writer_profile_names_prompt_intent(self):
        profile = WriterProfile(
            name="alchemy-research",
            audience="WeChat readers",
            prompt_style="hardcore investment research",
        )

        self.assertEqual(profile.name, "alchemy-research")
        self.assertIn("investment", profile.prompt_style)

    def test_compare_evaluation_names_compared_paths(self):
        evaluation = CompareEvaluation(
            name="caption-vs-audio",
            left_path="caption",
            right_path="audio-transcription",
            output_name="comparison.md",
        )

        self.assertEqual(evaluation.left_path, "caption")
        self.assertEqual(evaluation.output_name, "comparison.md")


if __name__ == "__main__":
    unittest.main()
