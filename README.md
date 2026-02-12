# 🔮 UpgradeSage

Instant breaking-change analysis between two versions of any Git repo, powered by Azure AI Foundry.

## Architecture

```
/api   → Python FastAPI backend (diff extraction + LLM analysis)
/web   → Vite + React frontend  (form + Markdown report viewer)
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Git** installed on the machine
- An **Azure AI Foundry** (Azure OpenAI) endpoint with a deployed chat model

---

## Required Environment Variables

| Variable | Description |
|---|---|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Your Azure AI Foundry resource endpoint (e.g. `https://myresource.openai.azure.com`) |
| `AZURE_AI_FOUNDRY_API_KEY` | API key for the resource |
| `AZURE_AI_FOUNDRY_MODEL` | Deployment name (default: `gpt-4o`) |

---

## Running the Backend

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set env vars
export AZURE_AI_FOUNDRY_ENDPOINT="https://..."
export AZURE_AI_FOUNDRY_API_KEY="sk-..."
export AZURE_AI_FOUNDRY_MODEL="gpt-4o"

uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**

---

## Running the Frontend

```bash
cd web
npm install
npm run dev
```

Frontend runs at **http://localhost:5173** and proxies `/api/*` → `localhost:8000`.

---

## Example cURL Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repoUrl": "https://github.com/expressjs/express",
    "fromRef": "4.18.2",
    "toRef": "4.19.2",
    "githubToken": null
  }'
```

---

## Response Shape

```json
{
  "riskScore": 42,
  "breakingChanges": [
    {
      "title": "Removed export X",
      "details": "Function X was removed from module Y",
      "mitigations": ["Use Z instead", "Add polyfill"]
    }
  ],
  "markdownReport": "## Breaking Changes\n..."
}
```

---

## License

MIT
