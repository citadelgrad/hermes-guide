import os
import unittest

os.environ.setdefault("HERMES_GUIDE_ADMIN_TOKEN", "test-token")
os.environ.setdefault("LIGHTRAG_DATA_DIR", "/tmp/hermes-guide-test-data")

from backend.main import _intent_queries_from_payload, _merge_intent_contexts, QueryRequest


class MixedIntentRetrievalTests(unittest.TestCase):
    def test_splits_goal_into_intent_queries_with_aliases(self):
        payload = QueryRequest(
            goal="I want Hermes to help me review code, use TDD, and summarize YouTube transcripts.",
            skills_list=["software-development-workflows"],
            soul_md="## Workflow\nCoding and research.",
            max_results=8,
        )

        intents = _intent_queries_from_payload(payload, "## Workflow\nCoding and research.")
        intent_text = "\n".join(intent["query"] for intent in intents).lower()
        keyword_text = "\n".join(" ".join(intent["keywords"]) for intent in intents).lower()

        self.assertGreaterEqual(len(intents), 3)
        self.assertIn("review code", intent_text)
        self.assertIn("test-driven development", intent_text)
        self.assertIn("youtube", intent_text)
        self.assertIn("transcript", keyword_text)

    def test_merge_preserves_each_intent_before_broad_truncation(self):
        contexts = [
            {"intent": "review code", "context": "Code Review skill context\nshared line"},
            {"intent": "use TDD", "context": "Test-Driven Development context\nshared line"},
            {"intent": "summarize YouTube transcripts", "context": "Youtube transcript context\nshared line"},
            {"intent": "combined goal", "context": "generic Hermes context " * 200},
        ]

        merged = _merge_intent_contexts(contexts, max_chars=900)
        lower = merged.lower()

        self.assertIn("code review", lower)
        self.assertIn("test-driven", lower)
        self.assertIn("youtube", lower)
        self.assertEqual(lower.count("shared line"), 1)
        self.assertLessEqual(len(merged), 900)


if __name__ == "__main__":
    unittest.main()
