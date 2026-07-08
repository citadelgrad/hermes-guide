import unittest
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.run_retrieval_evals import call_query_live, generate_report, langfuse_configured, score_response


class TestRetrievalEvalRunner(unittest.TestCase):
    """Unit tests for retrieval eval runner scoring logic (TDD red phase)."""

    def setUp(self):
        """Common fixture data for all tests."""
        self.case_pass = {
            "id": "coding_tdd_code_review",
            "goal": "Learn TDD and code review best practices",
            "skills_list": ["test-driven development", "code review"],
            "soul_md": "I'm learning Python and want to improve my testing skills.",
            "expected_terms": ["test", "review"],
            "max_latency_ms": 5000,
        }

        self.response_pass = {
            "status": 200,
            "context_lines": 12,
            "recommendations": ["intro to TDD", "code review checklist"],
            "expected_terms_found": ["test", "review"],
            "forbidden_terms_found": [],
        }

    def test_passes_when_all_expected_terms_present(self):
        """Test passes when response contains all expected terms."""
        result = score_response(self.case_pass, self.response_pass)
        self.assertTrue(result["passed"], "Should pass when all expected terms present")

    def test_fails_when_expected_term_missing(self):
        """Test fails when a required expected term is missing from response."""
        response = self.response_pass.copy()
        response["expected_terms_found"] = ["test"]  # missing "review"
        result = score_response(self.case_pass, response)
        self.assertFalse(result["passed"], "Should fail when expected term missing")
        self.assertIn("expected_terms_found", result["reason"].lower(),
                      "Failure reason should mention missing expected terms")

    def test_fails_when_forbidden_term_present(self):
        """Test fails when response contains a forbidden term."""
        case = self.case_pass.copy()
        case["forbidden_terms"] = ["calendar", "email"]
        response = self.response_pass.copy()
        response["forbidden_terms_found"] = ["calendar"]
        result = score_response(case, response)
        self.assertFalse(result["passed"], "Should fail when forbidden term present")
        self.assertIn("forbidden_terms_found", result["reason"].lower(),
                      "Failure reason should mention forbidden terms")

    def test_fails_when_context_lines_below_minimum(self):
        """Test fails when context_lines is below minimum (10 default or case-specified)."""
        response = self.response_pass.copy()
        response["context_lines"] = 7
        case = self.case_pass.copy()
        case["min_context_lines"] = 10
        result = score_response(case, response)
        self.assertFalse(result["passed"], "Should fail when context_lines below minimum")
        self.assertIn("context_lines", result["reason"].lower(),
                      "Failure reason should mention context_lines")

    def test_fails_on_non_200_status(self):
        """Test fails when HTTP status is not 200."""
        response = self.response_pass.copy()
        response["status"] = 503
        result = score_response(self.case_pass, response)
        self.assertFalse(result["passed"], "Should fail when status is not 200")
        self.assertIn("status", result["reason"].lower(),
                      "Failure reason should mention status code")

    def test_produces_json_report_with_summary_and_cases(self):
        """Test that generate_report produces JSON with summary and cases list."""
        cases = [self.case_pass]
        responses = [self.response_pass]
        report = generate_report(cases, responses)

        self.assertIsInstance(report, dict, "Report should be a dictionary")
        self.assertIn("summary", report, "Report should contain summary")
        self.assertIn("cases", report, "Report should contain cases list")

        summary = report["summary"]
        self.assertIn("total", summary, "Summary should have total count")
        self.assertIn("passed", summary, "Summary should have passed count")
        self.assertIn("failed", summary, "Summary should have failed count")

        cases_list = report["cases"]
        self.assertIsInstance(cases_list, list, "Cases should be a list")
        self.assertEqual(len(cases_list), 1, "Should have 1 case result")

    def test_handles_empty_recommendations_without_crashing(self):
        """Test that scorer handles empty recommendations list gracefully."""
        response = self.response_pass.copy()
        response["recommendations"] = []
        result = score_response(self.case_pass, response)
        self.assertIsInstance(result, dict, "Should return result dict even with empty recommendations")
        self.assertIn("passed", result, "Result should have passed key")

    def test_handles_malformed_fixture_body_with_clear_error(self):
        """Test that scorer raises clear error for malformed fixture body."""
        response = {}  # missing required fields: status, context_lines, etc.
        with self.assertRaises((KeyError, TypeError, ValueError)) as ctx:
            score_response(self.case_pass, response)
        error_msg = str(ctx.exception)
        self.assertTrue(
            len(error_msg) > 0,
            "Error message should be descriptive (not empty)"
        )

    def test_live_query_sends_langfuse_session_header_when_provided(self):
        """Live eval requests propagate the generated Langfuse session id to the API."""
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"recommendations": [], "context_lines": 10}).encode()

        captured = {}

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            response = call_query_live("https://example.test", self.case_pass, session_id="eval-session-123")

        self.assertEqual(response["status"], 200)
        self.assertEqual(captured["headers"].get("X-langfuse-session-id"), "eval-session-123")
        self.assertEqual(captured["timeout"], 30)

    def test_langfuse_requires_public_and_secret_key(self):
        """Langfuse submission is disabled unless both required credentials are present."""
        with patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk"}, clear=True):
            self.assertFalse(langfuse_configured())
        with patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}, clear=True):
            self.assertTrue(langfuse_configured())


if __name__ == "__main__":
    unittest.main()
