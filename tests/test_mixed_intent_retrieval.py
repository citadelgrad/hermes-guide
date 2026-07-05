import os
import unittest
from unittest.mock import patch

os.environ.setdefault("HERMES_GUIDE_ADMIN_TOKEN", "test-token")
os.environ.setdefault("LIGHTRAG_DATA_DIR", "/tmp/hermes-guide-test-data")

import backend.main as main
from backend.main import QueryRequest, _build_rerank_model_func, _intent_queries_from_payload, _merge_intent_contexts, _query_param_for_intent


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
        self.assertEqual(len(intents), 3)
        self.assertIn("review code", intent_text)
        self.assertIn("test-driven development", intent_text)
        self.assertIn("youtube", intent_text)
        self.assertIn("transcript", keyword_text)
        self.assertNotIn("combined goal", {intent["intent"] for intent in intents})

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

    def test_query_param_disables_rerank_when_no_model_is_configured(self):
        payload = QueryRequest(goal="Review code", max_results=20)
        intent = {"keywords": ["review", "code", "pull request"]}

        with patch.object(main, "rerank_model_func", None):
            param = _query_param_for_intent(payload, intent)

        self.assertFalse(param.enable_rerank)
        self.assertEqual(param.top_k, 8)
        self.assertEqual(param.chunk_top_k, 20)
        self.assertIn("pull request", param.ll_keywords)

    def test_query_param_enables_rerank_when_model_is_configured(self):
        payload = QueryRequest(goal="Review code", max_results=5)
        intent = {"keywords": ["review", "code"]}

        with patch.object(main, "rerank_model_func", object()):
            param = _query_param_for_intent(payload, intent)

        self.assertTrue(param.enable_rerank)
        self.assertEqual(param.top_k, 5)
        self.assertEqual(param.chunk_top_k, 6)
        self.assertEqual(param.max_entity_tokens, 2500)
        self.assertEqual(param.max_relation_tokens, 3500)
        self.assertEqual(param.max_total_tokens, 9000)

    def test_build_rerank_model_func_detects_jina_key(self):
        with patch.dict(os.environ, {"JINA_API_KEY": "test-key"}, clear=True):
            func = _build_rerank_model_func()

        self.assertIsNotNone(func)
        self.assertEqual(func.keywords["model"], "jina-reranker-v3")

    def test_query_param_allows_env_overrides_for_rerank_volume(self):
        payload = QueryRequest(goal="Review code", max_results=20)
        intent = {"keywords": ["review", "code"]}
        env = {
            "RERANK_TOP_K": "4",
            "RERANK_CHUNK_TOP_K": "3",
            "RERANK_MAX_ENTITY_TOKENS": "900",
            "RERANK_MAX_RELATION_TOKENS": "1200",
            "RERANK_MAX_TOTAL_TOKENS": "4000",
        }

        with patch.object(main, "rerank_model_func", object()), patch.dict(os.environ, env, clear=False):
            param = _query_param_for_intent(payload, intent)

        self.assertEqual(param.top_k, 4)
        self.assertEqual(param.chunk_top_k, 3)
        self.assertEqual(param.max_entity_tokens, 900)
        self.assertEqual(param.max_relation_tokens, 1200)
        self.assertEqual(param.max_total_tokens, 4000)


if __name__ == "__main__":
    unittest.main()
