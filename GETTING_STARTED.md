# 🔮 UpgradeSage — Getting Started Guide

> **Instant breaking-change analysis between two versions of any GitHub repo,
> powered by Azure AI Foundry.**

---

## 📋 What Is UpgradeSage?

UpgradeSage is a lightweight web tool that answers the question:

> *"What will break if I upgrade from version X to version Y?"*

You paste a GitHub repo URL and two version tags — UpgradeSage clones the repo,
extracts a diff, sends it to an Azure AI Foundry LLM, and streams back a
structured report with:

| Output | Description |
|--------|-------------|
| **Risk Score** | 0–100 severity rating (green / yellow / red) |
| **Breaking Changes** | Itemized list with titles, details, and mitigations |
| **Markdown Report** | Full human-readable analysis |

Results stream in real-time via Server-Sent Events (SSE) so you see live
progress as the backend works.

---

## 🏗️ Architecture

```
┌─────────────────────┐        SSE stream         ┌──────────────────────────┐
│   React Frontend    │ ◄──────────────────────── │   FastAPI Backend        │
│   (Vite · port 5173)│ ─── POST /analyze ──────► │   (uvicorn · port 8000)  │
└─────────────────────┘                            └────────┬─────────────────┘
                                                            │
                                                   ┌───────▼──────────┐
                                                   │  git fetch       │
                                                   │  (shallow clone) │
                                                   └───────┬──────────┘
                                                            │
                                                   ┌───────▼──────────┐
                                                   │  Azure AI Foundry│
                                                   │  (gpt-4.1 LLM)  │
                                                   └──────────────────┘
```

| Component | Tech | Port |
|-----------|------|------|
| Frontend  | Vite + React 18 + react-markdown | `5173` |
| Backend   | Python 3.11+ · FastAPI · uvicorn | `8000` |
| LLM       | Azure AI Foundry (Azure OpenAI) | — |

The frontend calls the backend **directly** on port 8000 (bypassing Vite's
proxy) so SSE events stream without buffering.

---

## ✅ Prerequisites

Before you begin, make sure you have:

- [ ] **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- [ ] **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- [ ] **Git** — [git-scm.com](https://git-scm.com/)
- [ ] **Azure AI Foundry resource** with a deployed chat model
  (e.g. `gpt-4.1`, `gpt-4o`)

### Azure AI Foundry Setup

You need three values from Azure:

| Value | Where to find it |
|-------|-------------------|
| **Endpoint** | Azure Portal → your AI Services resource → *Keys and Endpoint* |
| **API Key** | Same page — copy *Key 1* or *Key 2* |
| **Model / Deployment name** | Azure AI Foundry Studio → *Deployments* |

---

## 🚀 Quick Start (5 minutes)

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd 2026Hackfest
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your real values:

```dotenv
AZURE_AI_FOUNDRY_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_AI_FOUNDRY_API_KEY=your-api-key-here
AZURE_AI_FOUNDRY_MODEL=gpt-4.1
```

> ⚠️ **Never commit `.env`** — it is already in `.gitignore`.

### 3. Start the backend

```bash
cd api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Start the frontend (new terminal)

```bash
cd web
npm install
npm run dev
```

You should see:

```
  VITE v5.4.x  ready in ~300ms
  ➜  Local:   http://localhost:5173/
```

### 5. Open the app

Navigate to **http://localhost:5173** in your browser.

---

## 🎮 Using the App

1. **Paste a GitHub repo URL**
   - Example: `https://github.com/home-assistant/core`

2. **Enter the "From" version** (older tag/branch/SHA)
   - Example: `2024.12.5`

3. **Enter the "To" version** (newer tag/branch/SHA)
   - Example: `2025.2.1`

4. **Click "🚀 Analyze Upgrade"**

5. **Watch the Activity Log** — you'll see real-time progress:
   - `Cloning repo…`
   - `Fetching refs…`
   - `Generating diff…`
   - `Calling Azure AI Foundry…`
   - `✅ Report ready!`

6. **Review the results:**
   - A color-coded **Risk Score** badge (green ≤ 30 / yellow ≤ 65 / red > 65)
   - A full **Markdown report** with breaking changes, details, and mitigations

---

## 🧪 Testing with cURL

You can also test the backend directly:

```bash
curl -N -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repoUrl": "https://github.com/expressjs/express",
    "fromRef": "4.18.2",
    "toRef": "4.19.2"
  }'
```

> The `-N` flag disables curl's output buffering so you see SSE events in real-time.

The response is a stream of SSE events:

```
event: status
data: {"message": "Cloning repo..."}

event: status
data: {"message": "Generating diff (1234 chars)..."}

event: result
data: {"riskScore": 42, "breakingChanges": [...], "markdownReport": "..."}
```

---

## 📁 Project Structure

```
2026Hackfest/
├── .env                  # Your secrets (git-ignored)
├── .env.example          # Template with placeholders
├── .gitignore
├── README.md
├── GETTING_STARTED.md    # ← You are here
│
├── api/                  # Python backend
│   ├── main.py           # FastAPI app – SSE streaming, git diff, LLM call
│   ├── requirements.txt  # Python dependencies
│   └── .venv/            # Virtual environment (git-ignored)
│
└── web/                  # React frontend
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx      # React entry point
        ├── App.jsx       # Main component – form, SSE consumer, report
        └── App.css       # Dark theme styles
```

---

## ⚙️ How It Works Under the Hood

1. **Shallow Fetch** — Instead of cloning the entire repo, UpgradeSage runs:
   ```
   git init --bare <tmpdir>
   git fetch --depth=1 origin tag <from_ref> tag <to_ref>
   ```
   This downloads only the two commits, making even huge repos
   (e.g. home-assistant/core with 751k+ objects) complete in ~15 seconds
   instead of timing out.

2. **Diff Extraction** — A `git diff` between the two fetched refs produces
   the raw changeset. Diffs are truncated to ~120k characters (~30k tokens)
   to stay within LLM context limits.

3. **LLM Analysis** — The diff is sent to Azure AI Foundry with a structured
   prompt requesting JSON output containing `riskScore`,
   `breakingChanges[]`, and `markdownReport`.

4. **SSE Streaming** — Progress events stream to the frontend as they happen:
   `status` events for progress, `error` for failures, and `result` for the
   final report. The frontend consumes these via `ReadableStream`.

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| **"Failed to fetch"** | Make sure the backend is running on port 8000 |
| **CORS errors** | Backend already allows all origins — check browser extensions |
| **Git timeout** | Large repos may take 15–30s; the shallow fetch minimizes this |
| **Empty diff** | The two refs may point to the same commit |
| **"Azure credentials not configured"** | Check your `.env` file has all 3 values set |
| **Rate limit from Azure** | Wait a moment and retry; or increase model capacity in Azure Portal |

---

## 📜 License

MIT
