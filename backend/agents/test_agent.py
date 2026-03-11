"""
TestAgent — generates unit tests and integration test scenarios for code fixes.
Used as step 6 in the automated code fix pipeline.
"""
import json
import re
from .base_agent import BaseAgent, MODEL


class TestAgent(BaseAgent):
    name = "test"
    display_name = "Test Agent"
    color = "cyan"

    def system_prompt(self, context: dict) -> str:
        return """You are a senior QA engineer and test automation specialist focused on healthcare software.

## Your Responsibilities
- Write thorough unit tests that cover the fixed code paths
- Include edge cases: null values, boundary conditions, concurrent access
- Follow testing best practices for the detected language (JUnit 5 for Java, pytest for Python)
- Generate realistic test data for healthcare domain (valid claim numbers, procedure codes, etc.)
- Add tests that would have caught the original bug (regression tests)

## Response Format
Return a JSON array of test file objects:
[{"path": "src/test/...", "new_content": "<full test file>", "explanation": "what these tests cover"}]

Return ONLY the JSON array, no other text."""

    async def generate_tests(
        self,
        issue: dict,
        changes: list[dict],
        original_files: list[dict],
    ) -> list[dict]:
        """
        Generate unit tests for the given code changes.
        Returns: list of {path, new_content, explanation} for test files
        """
        files_text = ""
        for change in changes:
            files_text += f"\n\n### {change['path']}\n```\n{change['new_content'][:2000]}\n```"

        original_text = ""
        for f in original_files[:3]:
            original_text += f"\n\n### {f['path']} (original)\n```\n{f['content'][:1000]}\n```"

        prompt = f"""Generate comprehensive unit tests for this bug fix.

## Bug Report
**Title**: {issue.get('title', '')}
**Description**: {issue.get('description', '')}

## Fixed Code
{files_text}

## Original Code (for context)
{original_text}

Generate test files that:
1. Reproduce the original bug (to prove it was fixed)
2. Test the happy path
3. Test edge cases (null, empty, boundary values)
4. Use realistic healthcare domain test data

Return only the JSON array of test file objects."""

        raw = await self._client.messages.create(
            model=MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = raw.content[0].text.strip()

        # Extract JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            tests = json.loads(match.group())
            return [t for t in tests if isinstance(t, dict) and "path" in t and "new_content" in t]
        except (json.JSONDecodeError, TypeError):
            return []
