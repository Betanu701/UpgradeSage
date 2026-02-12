import { useState } from "react";
import ReactMarkdown from "react-markdown";

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [fromRef, setFromRef] = useState("");
  const [toRef, setToRef] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repoUrl, fromRef, toRef }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${resp.status}`);
      }
      setResult(await resp.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>🔮 UpgradeSage</h1>
        <p className="subtitle">Instant breaking-change analysis between two versions</p>
      </header>

      <section className="form-card">
        <label>
          GitHub Repo URL
          <input
            type="text"
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
        </label>

        <div className="row">
          <label>
            From (tag / branch / SHA)
            <input
              type="text"
              placeholder="v1.0.0"
              value={fromRef}
              onChange={(e) => setFromRef(e.target.value)}
            />
          </label>
          <label>
            To (tag / branch / SHA)
            <input
              type="text"
              placeholder="v2.0.0"
              value={toRef}
              onChange={(e) => setToRef(e.target.value)}
            />
          </label>
        </div>

        <button onClick={analyze} disabled={loading || !repoUrl || !fromRef || !toRef}>
          {loading ? "Analyzing…" : "🚀 Analyze Upgrade"}
        </button>
      </section>

      {loading && (
        <div className="spinner-area">
          <div className="spinner" />
          <p>Cloning repo &amp; consulting the LLM — hang tight…</p>
        </div>
      )}

      {error && <div className="error-card">❌ {error}</div>}

      {result && (
        <section className="result-card">
          <div className="risk-badge" data-level={
            result.riskScore <= 30 ? "low" : result.riskScore <= 65 ? "med" : "high"
          }>
            Risk Score: <strong>{result.riskScore}</strong>/100
          </div>
          <div className="markdown-body">
            <ReactMarkdown>{result.markdownReport}</ReactMarkdown>
          </div>
        </section>
      )}
    </div>
  );
}
