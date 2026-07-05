import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib import request


REPO = Path(__file__).resolve().parents[1]
SKILL_PATHS = [REPO / "skill/guide.md", REPO / "skill/v1/guide.md"]


class GuideSkillUserExperienceTests(unittest.TestCase):
    def test_skill_has_no_token_friction_and_prompts_for_only_url(self):
        for path in SKILL_PATHS:
            with self.subTest(path=path.relative_to(REPO)):
                text = path.read_text()

                self.assertIn("HERMES_GUIDE_URL", text)
                self.assertNotIn("HERMES_GUIDE_QUERY_TOKEN", text)
                self.assertNotIn("Authorization: Bearer", text)
                self.assertIn("No token", (REPO / "README.md").read_text())

    def test_skill_preflight_gives_actionable_missing_url_message(self):
        skill_text = (REPO / "skill/guide.md").read_text()

        self.assertIn("echo \"URL=${HERMES_GUIDE_URL:-MISSING}\"", skill_text)
        self.assertIn("The `/guide` skill needs `HERMES_GUIDE_URL` configured", skill_text)
        self.assertIn("Default: `https://hermes-guide.fly.dev`", skill_text)
        self.assertIn("Do not proceed", skill_text)

    def test_skill_asks_one_goal_question_before_calling_api(self):
        skill_text = (REPO / "skill/guide.md").read_text()
        question = "What are you trying to accomplish with Hermes?"

        self.assertEqual(skill_text.count(question), 1)
        self.assertLess(skill_text.index("## Step 3"), skill_text.index("## Step 4"))
        self.assertLess(skill_text.index("## Step 4"), skill_text.index("## Step 5"))

    def test_skill_payload_command_handles_quotes_newlines_and_installed_skills(self):
        goal = "Review code, use TDD, and summarize YouTube transcripts with quotes like \"ship it\"."
        soul = "## Communication\nBe direct.\nUse `code` and 'quotes'.\n"

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hermes = home / ".hermes"
            skills = hermes / "skills"
            skills.mkdir(parents=True)
            (hermes / "soul.md").write_text(soul)
            for name in ["software-development-workflows", "duckduckgo-search"]:
                (skills / name).mkdir()
            goal_file = home / "goal.txt"
            payload_file = home / "payload.json"
            goal_file.write_text(goal)

            script = """
set -euo pipefail
SOUL=$(cat "$HOME/.hermes/soul.md" 2>/dev/null || echo "")
SKILLS=$(ls "$HOME/.hermes/skills/" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
GOAL=$(cat "$GOAL_FILE")
MAX=${HERMES_GUIDE_MAX_RESULTS:-5}
PAYLOAD=$(jq -n \
  --arg soul   "$SOUL" \
  --arg skills "$SKILLS" \
  --arg goal   "$GOAL" \
  --argjson max "$MAX" \
  '{soul_md: $soul,
    skills_list: ($skills | split(",") | map(select(length > 0))),
    goal: $goal,
    max_results: $max}')
printf '%s' "$PAYLOAD" > "$PAYLOAD_FILE"
"""
            env = os.environ.copy() | {
                "HOME": str(home),
                "GOAL_FILE": str(goal_file),
                "PAYLOAD_FILE": str(payload_file),
                "HERMES_GUIDE_MAX_RESULTS": "8",
            }
            subprocess.run(["bash", "-lc", script], cwd=REPO, env=env, check=True, timeout=30)

            payload = json.loads(payload_file.read_text())
            self.assertEqual(payload["goal"], goal)
            self.assertEqual(payload["soul_md"], soul.rstrip("\n"))
            self.assertEqual(payload["max_results"], 8)
            self.assertEqual(set(payload["skills_list"]), {"software-development-workflows", "duckduckgo-search"})

    def test_skill_presentation_contract_is_three_user_facing_sections(self):
        skill_text = (REPO / "skill/guide.md").read_text()

        for heading in ["### Section 1: SOUL.md", "### Section 2: Skills to install", "### Section 3: Quick wins"]:
            self.assertIn(heading, skill_text)

        self.assertIn("Specific over generic", skill_text)
        self.assertIn("Priority first", skill_text)
        self.assertIn("No filler", skill_text)


@unittest.skipUnless(os.environ.get("HERMES_GUIDE_LIVE_TESTS") == "1", "set HERMES_GUIDE_LIVE_TESTS=1 for live API UX acceptance")
class LiveGuideSkillUserExperienceTests(unittest.TestCase):
    def test_live_mixed_intent_context_supports_user_visible_sections(self):
        api = os.environ.get("HERMES_GUIDE_URL", "https://hermes-guide.fly.dev")
        payload = {
            "goal": "I want Hermes to help me review code, use TDD, and summarize YouTube transcripts.",
            "skills_list": ["software-development-workflows", "duckduckgo-search"],
            "soul_md": "## Workflow\nI use Hermes for coding and research.\n",
            "max_results": 8,
        }
        req = request.Request(
            f"{api}/query",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode()
            self.assertEqual(resp.status, 200)

        data = json.loads(body)
        self.assertGreaterEqual(len(data.get("recommendations", [])), 1)
        lower = body.lower()
        for expected in ["code review", "test-driven", "youtube", "transcript"]:
            self.assertIn(expected, lower)

        categories = {rec.get("category") for rec in data["recommendations"]}
        self.assertIn("knowledge_context", categories)


if __name__ == "__main__":
    unittest.main()
