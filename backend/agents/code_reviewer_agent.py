"""
CodeReviewerAgent — reviews code changes for correctness, security, design patterns.
Used as step 5 in the automated code fix pipeline after CodeFixAgent generates a fix.
"""
import json
import re
from .base_agent import BaseAgent, MODEL


class CodeReviewerAgent(BaseAgent):
    name = "code_reviewer"
    display_name = "Code Reviewer"
    color = "amber"

    def system_prompt(self, context: dict) -> str:
        return """You are a senior software engineer conducting a thorough peer code review.

## Review Criteria
- **Correctness**: Does the fix actually solve the stated issue?
- **Security**: No new vulnerabilities introduced (null pointer, injection, auth bypass)
- **Healthcare Compliance**: HIPAA-safe patterns, proper PHI handling
- **Design**: Follows SOLID principles, appropriate abstraction level
- **Performance**: No O(n²) where O(n) suffices, no unnecessary DB calls
- **Edge Cases**: Handles nulls, empty lists, boundary conditions

## Response Format
Keep your review concise and actionable (≤ 200 words). Structure as:
**Verdict**: APPROVED / APPROVED WITH COMMENTS / REQUEST CHANGES
**Summary**: One sentence
**Comments**: Bullet list of specific observations (max 5)"""

    async def review_fix(
        self,
        issue: dict,
        changes: list[dict],
        original_files: list[dict],
    ) -> dict:
        """
        Review a set of code changes.
        Returns: {approved: bool, verdict: str, summary: str, comments: list[str]}
        """
        # Build a diff-like representation
        file_reviews = []
        original_map = {f["path"]: f["content"] for f in original_files}
        for change in changes:
            path = change["path"]
            original = original_map.get(path, "(new file)")
            new_content = change["new_content"]
            explanation = change.get("explanation", "")
            file_reviews.append(
                f"### {path}\n"
                f"**Change rationale**: {explanation}\n\n"
                f"**Original** (excerpt):\n```\n{original[:1500]}\n```\n\n"
                f"**New version** (excerpt):\n```\n{new_content[:1500]}\n```"
            )

        prompt = f"""Please review this code fix for the following issue:

## Issue
**Title**: {issue.get('title', '')}
**Description**: {issue.get('description', '')}

## Changed Files
{chr(10).join(file_reviews)}

Provide your code review verdict and comments."""

        raw = await self._client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=self.system_prompt({}),
            messages=[{"role": "user", "content": prompt}],
        )
        text = raw.content[0].text

        # Parse verdict
        approved = "REQUEST CHANGES" not in text.upper()
        verdict = "APPROVED WITH COMMENTS"
        if "REQUEST CHANGES" in text.upper():
            verdict = "REQUEST CHANGES"
        elif "APPROVED WITH COMMENTS" not in text.upper() and "APPROVED" in text.upper():
            verdict = "APPROVED"

        # Extract bullet comments
        comments = re.findall(r"[-•]\s+(.+)", text)

        return {
            "approved": approved,
            "verdict": verdict,
            "summary": text.split("\n")[0].replace("**Summary**:", "").strip(),
            "comments": comments[:5],
            "full_review": text,
        }
