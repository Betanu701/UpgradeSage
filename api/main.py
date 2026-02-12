"""UpgradeSage – ultra-minimal FastAPI backend with SSE progress streaming."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load .env from project root (one level up from /api)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upgradesage")

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

def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Events message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _clone_and_diff(repo_url: str, from_ref: str, to_ref: str, token: str | None, send: list) -> str:
    """Fetch only the two requested refs into a bare repo, then diff them.
    `send` is a list we append SSE strings to (sync context)."""
    tmp = tempfile.mkdtemp(prefix="upgradesage_")
    try:
        clone_url = repo_url
        if token and "github.com" in repo_url:
            clone_url = repo_url.replace("https://", f"https://{token}@")

        git_dir = os.path.join(tmp, "repo.git")

        # ── Step: Init bare repo ──
        send.append(_sse("status", {"step": "init", "message": f"📦 Initializing local repo for {repo_url} …"}))
        log.info("Init bare repo for %s", repo_url)
        subprocess.run(
            ["git", "init", "--bare", "-q", git_dir],
            check=True, capture_output=True, text=True, timeout=10,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", clone_url],
            cwd=git_dir, check=True, capture_output=True, text=True, timeout=10,
        )

        # ── Step: Fetch only the two refs (shallow) ──
        # Try fetching as tags first (most common for version comparisons)
        send.append(_sse("status", {"step": "fetch", "message": f"⬇️  Fetching {from_ref} and {to_ref} (shallow) …"}))
        log.info("Fetching refs %s, %s from %s", from_ref, to_ref, repo_url)
        t0 = time.time()

        # First attempt: fetch as tags (fastest path)
        tag_result = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", "tag", from_ref, "tag", to_ref],
            cwd=git_dir, capture_output=True, text=True, timeout=300,
        )

        if tag_result.returncode != 0:
            # Fallback: fetch as generic refspecs (branches, SHAs, etc.)
            send.append(_sse("status", {"step": "fetch", "message": "🔀 Not tags – fetching as branches/SHAs …"}))
            log.info("Tag fetch failed, trying generic fetch")
            for ref in (from_ref, to_ref):
                # Try fetching the ref and storing it as a local ref we can diff
                res = subprocess.run(
                    ["git", "fetch", "--depth=1", "origin", f"{ref}"],
                    cwd=git_dir, capture_output=True, text=True, timeout=300,
                )
                if res.returncode != 0:
                    # Last resort: full unshallow fetch of the ref
                    send.append(_sse("status", {"step": "fetch", "message": f"⚠️  Shallow fetch failed for {ref}, trying full fetch …"}))
                    subprocess.run(
                        ["git", "fetch", "origin", ref],
                        cwd=git_dir, capture_output=True, text=True, timeout=300,
                    )
                # Create a local ref so `git diff` can find it
                # Get the SHA from FETCH_HEAD and tag it locally
                sha_result = subprocess.run(
                    ["git", "rev-parse", "FETCH_HEAD"],
                    cwd=git_dir, capture_output=True, text=True, timeout=10,
                )
                if sha_result.returncode == 0 and sha_result.stdout.strip():
                    subprocess.run(
                        ["git", "tag", "-f", f"_local_{ref}", sha_result.stdout.strip()],
                        cwd=git_dir, capture_output=True, text=True, timeout=10,
                    )

        elapsed = round(time.time() - t0, 1)
        send.append(_sse("status", {"step": "fetch", "message": f"✅ Refs fetched ({elapsed}s)"}))
        log.info("Fetch done in %ss", elapsed)

        # ── Step: Diff ──
        send.append(_sse("status", {"step": "diff", "message": f"📝 Computing diff {from_ref}..{to_ref} …"}))
        log.info("Running git diff %s %s", from_ref, to_ref)
        t0 = time.time()

        # Try direct ref names first, then fall back to _local_ tags
        result = subprocess.run(
            ["git", "diff", from_ref, to_ref, "--unified=5"],
            cwd=git_dir, capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            log.info("Direct diff failed, trying _local_ tags")
            result = subprocess.run(
                ["git", "diff", f"_local_{from_ref}", f"_local_{to_ref}", "--unified=5"],
                cwd=git_dir, capture_output=True, text=True, timeout=120,
            )

        diff_text = result.stdout
        elapsed = round(time.time() - t0, 1)
        lines = diff_text.count("\n")
        chars = len(diff_text)
        if not diff_text:
            stderr_hint = result.stderr.strip()[:200] if result.stderr else ""
            diff_text = f"(no diff output – refs may be identical or invalid. stderr: {stderr_hint})"
            send.append(_sse("status", {
                "step": "diff",
                "message": f"⚠️  No diff output ({elapsed}s) – refs may point to the same commit",
            }))
        else:
            send.append(_sse("status", {
                "step": "diff",
                "message": f"✅ Diff ready – {lines:,} lines, {chars:,} chars ({elapsed}s)",
            }))
        log.info("Diff: %d lines, %d chars", lines, chars)
        return diff_text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _build_prompt(diff_text: str) -> tuple[str, bool]:
    max_chars = 120_000
    truncated = False
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + "\n\n... [diff truncated] ..."
        truncated = True

    prompt = f"""You are an expert software maintainer. Here is a unified diff between two versions of a codebase.

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
    return prompt, truncated


async def _call_foundry(prompt: str) -> tuple[dict, dict]:
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

    log.info("Calling Azure AI Foundry: %s / %s", AZURE_ENDPOINT, AZURE_MODEL)
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            log.error("Foundry error %d: %s", resp.status_code, resp.text[:500])
            raise HTTPException(502, f"Foundry error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    log.info("LLM responded – tokens: prompt=%s, completion=%s",
             usage.get("prompt_tokens"), usage.get("completion_tokens"))

    # Strip markdown fences if the model wraps them
    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = "\n".join(content.split("\n")[:-1])

    try:
        return json.loads(content), usage
    except json.JSONDecodeError:
        return {
            "riskScore": -1,
            "breakingChanges": [],
            "markdownReport": f"⚠️ LLM returned non-JSON. Raw output:\n\n```\n{content}\n```",
        }, usage


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """SSE streaming endpoint – sends live progress, then the final result."""

    # Trim whitespace from inputs to prevent git fetch failures
    repo_url = req.repoUrl.strip()
    from_ref = req.fromRef.strip()
    to_ref = req.toRef.strip()
    github_token = req.githubToken.strip() if req.githubToken else None

    async def event_stream():
        messages: list[str] = []
        overall_t0 = time.time()

        # ── Git clone & diff (sync work, run in thread) ──
        try:
            yield _sse("status", {"step": "start", "message": f"🚀 Starting analysis: {repo_url}  {from_ref} → {to_ref}"})
            await asyncio.sleep(0)

            diff_text = await asyncio.to_thread(
                _clone_and_diff, repo_url, from_ref, to_ref, github_token, messages
            )
            for msg in messages:
                yield msg
                await asyncio.sleep(0)
            messages.clear()

        except subprocess.TimeoutExpired:
            yield _sse("error", {"message": "⏱️ Git operation timed out (120s)"})
            return
        except subprocess.CalledProcessError as exc:
            err = exc.stderr[:500] if isinstance(exc.stderr, str) else (exc.stderr.decode(errors="replace")[:500] if exc.stderr else str(exc))
            yield _sse("error", {"message": f"💥 Git error: {err}"})
            return
        except Exception as exc:
            yield _sse("error", {"message": f"💥 Unexpected error during clone: {exc}"})
            return

        # ── Build prompt ──
        prompt, truncated = _build_prompt(diff_text)
        trunc_note = " (truncated to 120k chars)" if truncated else ""
        yield _sse("status", {"step": "llm", "message": f"🤖 Sending diff to {AZURE_MODEL}{trunc_note} …"})
        await asyncio.sleep(0)

        # ── Call LLM ──
        try:
            t0 = time.time()
            result, usage = await _call_foundry(prompt)
            elapsed = round(time.time() - t0, 1)
            tok = f"prompt={usage.get('prompt_tokens', '?')}, completion={usage.get('completion_tokens', '?')}"
            yield _sse("status", {"step": "llm", "message": f"✅ LLM responded ({elapsed}s, {tok})"})
            await asyncio.sleep(0)
        except HTTPException as exc:
            yield _sse("error", {"message": f"💥 LLM call failed: {exc.detail}"})
            return
        except Exception as exc:
            yield _sse("error", {"message": f"💥 LLM call failed: {exc}"})
            return

        total = round(time.time() - overall_t0, 1)
        yield _sse("status", {"step": "done", "message": f"🏁 Analysis complete in {total}s"})

        # ── Final JSON result ──
        yield _sse("result", result)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
