"""
Demo seed script — creates the 3 Jira bug tickets for the healthcare-claims demo.

Usage:
    cd backend
    python demo_seed.py

Each ticket is created with:
  - Label: ai-fix          (triggers the autonomous pipeline)
  - Priority: High/Highest
  - Realistic healthcare bug description

After running this script:
  1. Start the backend:  python main.py
  2. Start the frontend: cd ../frontend && npm run dev
  3. Open http://localhost:5173 → click "AI Pipeline" tab
  4. The system will detect the ai-fix tickets within 30 seconds and
     automatically start fixing them — or click "Run Pipeline" to trigger manually.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv(override=True)

import httpx

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL    = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")

AUTH    = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


DEMO_BUGS = [
    {
        "summary": "NullPointerException in ClaimAdjudicationService when patient has no active coverage",
        "description": (
            "Production incident (P1): System throws NullPointerException when adjudicating "
            "claims for patients without an active coverage record.\n\n"
            "Stack trace:\n"
            "  at ClaimAdjudicationService.adjudicateClaim(ClaimAdjudicationService.java:87)\n"
            "  at ClaimController.adjudicateClaim(ClaimController.java:54)\n\n"
            "Root cause: claim.getPatient().getCoverage().getCoverageType() is called "
            "without a null check on getCoverage(). When a patient's coverage has lapsed "
            "or was never set up, getCoverage() returns null, causing NPE.\n\n"
            "Expected: Return AdjudicationResult.denied('No active coverage') instead of throwing.\n"
            "Affected: ~2% of daily claim volume (patients switching insurers mid-month).\n"
            "File: src/main/java/com/enterprise/healthcare/claims/service/ClaimAdjudicationService.java"
        ),
        "priority": "Highest",
        "labels": ["ai-fix", "production-incident", "claims-adjudication"],
    },
    {
        "summary": "Deductible calculation off-by-one: patients overcharged when deductible is exactly met",
        "description": (
            "Finance audit finding: Patients are being charged the full claim amount "
            "instead of only coinsurance (20%) when their year-to-date payments exactly "
            "equal the deductible threshold.\n\n"
            "Example: Patient with $1,500 deductible who has paid exactly $1,500 YTD "
            "submits a $500 claim. Expected patient responsibility: $100 (20% coinsurance). "
            "Actual: $500 (full claim amount charged incorrectly).\n\n"
            "Root cause: DeductibleCalculatorService.calculatePatientResponsibility() uses "
            "yearToDatePaid.compareTo(deductibleAmount) > 0 (strict greater-than) instead "
            "of >= 0. When YTD equals the deductible, the condition is false and the full "
            "claim is incorrectly assigned to the patient.\n\n"
            "Fix: Change > 0 to >= 0 in the comparison.\n"
            "File: src/main/java/com/enterprise/healthcare/claims/service/DeductibleCalculatorService.java"
        ),
        "priority": "High",
        "labels": ["ai-fix", "billing-error", "deductible"],
    },
    {
        "summary": "ConcurrentModificationException crashes batch claim processing when invalid claim lines present",
        "description": (
            "Batch processing failure: The nightly claim batch processor throws "
            "ConcurrentModificationException when any claim in the batch contains "
            "claim lines with zero or null billed amounts.\n\n"
            "Error:\n"
            "  java.util.ConcurrentModificationException\n"
            "  at ClaimAdjudicationService.validateClaimLines(ClaimAdjudicationService.java:189)\n\n"
            "Root cause: The validateClaimLines() method calls claimLines.remove(line) "
            "inside a for-each loop over the same list. Java's ArrayList does not permit "
            "structural modification during iteration.\n\n"
            "Fix: Replace the for-each + remove pattern with claimLines.removeIf() or "
            "use an Iterator with iterator.remove().\n"
            "File: src/main/java/com/enterprise/healthcare/claims/service/ClaimAdjudicationService.java"
        ),
        "priority": "High",
        "labels": ["ai-fix", "batch-processing", "concurrency"],
    },
]


async def get_issue_type(client: httpx.AsyncClient) -> str:
    """Find the best available issue type for this project."""
    resp = await client.get(
        f"{JIRA_BASE_URL}/rest/api/3/issue/createmeta",
        params={"projectKeys": JIRA_PROJECT_KEY, "expand": "projects.issuetypes"},
    )
    if resp.is_error:
        return "Task"
    projects = resp.json().get("projects", [])
    if not projects:
        return "Task"
    available = [it["name"] for it in projects[0].get("issuetypes", [])]
    for preferred in ("Task", "Story", "Bug"):
        if preferred in available:
            return preferred
    return available[0] if available else "Task"


async def create_jira_issue(client: httpx.AsyncClient, issue_type: str, bug: dict) -> dict:
    body = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     bug["summary"],
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": bug["description"]}
                ]}],
            },
            "issuetype": {"name": issue_type},
            "priority":  {"name": bug["priority"]},
            "labels":    bug["labels"],
        }
    }
    resp = await client.post(f"{JIRA_BASE_URL}/rest/api/3/issue", json=body)
    if resp.is_error:
        detail = resp.json()
        msgs = detail.get("errorMessages", [])
        errs = detail.get("errors", {})
        raise RuntimeError(f"Jira error {resp.status_code}: {'; '.join(msgs + list(errs.values()))}")
    data = resp.json()
    return {"key": data["key"], "url": f"{JIRA_BASE_URL}/browse/{data['key']}"}


async def main():
    if not JIRA_BASE_URL or not JIRA_EMAIL or not JIRA_API_TOKEN or not JIRA_PROJECT_KEY:
        print("ERROR: Missing Jira config in .env")
        print("  Required: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY")
        return

    print(f"\n{'='*60}")
    print(f"  Healthcare Claims Demo — Creating Jira Bug Tickets")
    print(f"  Project: {JIRA_PROJECT_KEY}  |  {JIRA_BASE_URL}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(auth=AUTH, headers=HEADERS, timeout=20) as client:
        issue_type = await get_issue_type(client)
        print(f"Using issue type: {issue_type}\n")

        created = []
        for i, bug in enumerate(DEMO_BUGS, 1):
            try:
                result = await create_jira_issue(client, issue_type, bug)
                created.append(result)
                print(f"[{i}/3] Created {result['key']}: {bug['summary'][:70]}…")
                print(f"       URL: {result['url']}")
            except RuntimeError as e:
                print(f"[{i}/3] FAILED: {e}")

    print(f"\n{'='*60}")
    print("  Done! Next steps:")
    print()
    print("  1. Start backend:   cd backend && python main.py")
    print("  2. Start frontend:  cd frontend && npm run dev")
    print("  3. Open:            http://localhost:5173")
    print("  4. Click:           'AI Pipeline' tab")
    print()
    print("  The system polls Jira every 30s for 'ai-fix' tickets.")
    print("  Or click 'Run Pipeline' and enter one of these keys:")
    for c in created:
        print(f"    - {c['key']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
