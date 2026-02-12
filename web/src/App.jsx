import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [fromRef, setFromRef] = useState("");
  const [toRef, setToRef] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const logEndRef = useRef(null);

  // Auto-scroll log feed
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const pushLog = (msg, type = "info") => {
    const ts = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { ts, msg, type }]);
  };

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLogs([]);

    pushLog("Connecting to backend…");

    // Hit the backend directly (port 8000) so SSE streams in real-time.
    // Vite's proxy buffers SSE, so we bypass it entirely.
    const backendOrigin = `${window.location.protocol}//${window.location.hostname}:8000`;

    try {
      const resp = await fetch(`${backendOrigin}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repoUrl: repoUrl.trim(), fromRef: fromRef.trim(), toRef: toRef.trim() }),
      });

      if (!resp.ok) {
        const body = await resp.text();
        let detail;
        try { detail = JSON.parse(body).detail; } catch { detail = null; }
        throw new Error(detail || `Server error ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse complete SSE messages (separated by double newline)
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // keep any incomplete trailing chunk

        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = "message";
          let data = "";
          for (const line of part.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7);
            else if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (!data) continue;

          try {
            const parsed = JSON.parse(data);
            if (eventType === "status") {
              pushLog(parsed.message, "status");
            } else if (eventType === "error") {
              pushLog(parsed.message, "error");
              setError(parsed.message);
            } else if (eventType === "result") {
              setResult(parsed);
              pushLog("✅ Report ready!", "success");
            }
          } catch {
            pushLog(`Unparseable event: ${data}`, "warn");
          }
        }
      }
    } catch (err) {
      pushLog(`Error: ${err.message}`, "error");
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

      {(loading || logs.length > 0) && (
        <section className="log-card">
          <h3>📡 Activity Log</h3>
          <div className="log-feed">
            {logs.map((l, i) => (
              <div key={i} className={`log-line log-${l.type}`}>
                <span className="log-ts">{l.ts}</span>
                <span className="log-msg">{l.msg}</span>
              </div>
            ))}
            {loading && (
              <div className="log-line log-info">
                <span className="log-ts">{new Date().toLocaleTimeString()}</span>
                <span className="log-msg blink">⏳ Working…</span>
              </div>
            )}
            <div ref={logEndRef} />
          </div>
        </section>
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
