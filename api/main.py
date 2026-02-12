"""UpgradeSage – ultra-minimal FastAPI backend."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env from project root (one level up from /api)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AZURE_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "")
AZURE_API_KEY = os.getenv("AZURE_AI_FOUNDRY_API_KEY", "")
AZURE_MODEL = os.getenv("AZURE_AI_FOUNDRY_MODEL", "gpt-4o")

app = FastAPI(title="UpgradeSage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    repoUrl: str
    fromRef: str
    toRef: str
    githubToken: str | None = None


class BreakingChange(BaseModel):
    title: str
    details: str
    mitigations: list[str]


class AnalyzeResponse(BaseModel):
    riskScore: int
    breakingChanges: list[BreakingChange]
    markdownReport: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clone_and_diff(repo_url: str, from_ref: str, to_ref: str, token: str | None) -> str:
    """Clone repo into a temp dir, fetch both refs, return unified diff."""
    tmp = tempfile.mkdtemp(prefix="upgradesage_")
    try:
        # Optionally inject token for private repos
        clone_url = repo_url
        if token and "github.com" in repo_url:
            clone_url = repo_url.replace("https://", f"https://{token}@")

        # Shallow clone default branch first
        subprocess.run(
            ["git", "clone", "--bare", "--filter=blob:none", clone_url, tmp + "/repo.git"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        git_dir = tmp + "/repo.git"

        # Fetch both refs explicitly (handles tags, branches, SHAs)
        for ref in (from_ref, to_ref):
            subprocess.run(
                ["git", "fetch", "origin", ref],
                cwd=git_dir,
                capture_output=True,
                timeout=60,
            )

        # Generate unified diff
        result = subprocess.run(
            ["git", "diff", from_ref, to_ref, "--unified=5"],
            cwd=git_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        diff_text = result.stdout
        if not diff_text:
            # Fallback: try with FETCH_HEAD style
            diff_text = "(no diff output – refs may be identical or invalid)"
        return diff_text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _build_prompt(diff_text: str) -> str:
    # Truncate diff if absurdly large (token budget ~120k chars ≈ 30k tokens)
    max_chars = 120_000
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + "\n\n... [diff truncated] ..."

    return f"""You are an expert software maintainer. Here is a unified diff between two versions of a codebase.

Identify:
- All *breaking changes* that would likely break consumers.
- Describe WHY each one is breaking.
- Provide specific mitigation steps or upgrade paths for each.
- Provide a risk score 0-100 (0 = trivial, 100 = catastrophic).

Return ONLY valid JSON (no markdown fences) with exactly this shape:
{{
  "riskScore": <number>,
  "breakingChanges": [
    {{
      "title": "<short title>",
      "details": "<why it is breaking>",
      "mitigations": ["<step 1>", "<step 2>"]
    }}
  ],
  "markdownReport": "<full human-readable Markdown report with headings, lists, risk badge>"
}}

Here is the full diff:

{diff_text}
"""


async def _call_foundry(prompt: str) -> dict:
    """Call Azure AI Foundry chat/completions endpoint."""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        raise HTTPException(500, "Azure AI Foundry env vars not set")

    url = f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_MODEL}/chat/completions?api-version=2024-12-01-preview"

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_API_KEY,
    }
    body = {
        "messages": [
            {"role": "system", "content": "You are UpgradeSage, an expert at analysing code diffs for breaking changes."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise HTTPException(502, f"Foundry error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

    content = data["choices"][0]["message"]["content"]

    # Strip markdown fences if the model wraps them
    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = "\n".join(content.split("\n")[:-1])

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Return a fallback so the frontend still gets something
        return {
            "riskScore": -1,
            "breakingChanges": [],
            "markdownReport": f"⚠️ LLM returned non-JSON. Raw output:\n\n```\n{content}\n```",
        }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    # 1. Clone + diff
    try:
        diff_text = _clone_and_diff(req.repoUrl, req.fromRef, req.toRef, req.githubToken)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Git operation timed out")
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            400,
            f"Git error: {exc.stderr.decode(errors='replace')[:500] if exc.stderr else str(exc)}",
        )

    # 2. Build prompt & call LLM
    prompt = _build_prompt(diff_text)
    result = await _call_foundry(prompt)

    return AnalyzeResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok"}
