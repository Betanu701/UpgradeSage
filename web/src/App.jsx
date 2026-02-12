import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [fromRef, setFromRef] = useState("");
  const [toRef, setToRef] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [tokenUsage, setTokenUsage] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [config, setConfig] = useState(null);
  const [startupInfo, setStartupInfo] = useState(null);
  const logEndRef = useRef(null);

  // Auto-scroll log feed
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);
  
  // Load startup configuration
  useEffect(() => {
    loadStartupInfo();
    loadTokenUsage();
  }, []);

  const backendOrigin = `${window.location.protocol}//${window.location.hostname}:8000`;

  const loadStartupInfo = async () => {
    try {
      const resp = await fetch(`${backendOrigin}/config/startup`);
      if (resp.ok) {
        const data = await resp.json();
        setStartupInfo(data);
      }
    } catch (err) {
      console.error("Failed to load startup info:", err);
    }
  };

  const loadTokenUsage = async () => {
    try {
      const resp = await fetch(`${backendOrigin}/config/token-usage`);
      if (resp.ok) {
        const data = await resp.json();
        setTokenUsage(data);
      }
    } catch (err) {
      console.error("Failed to load token usage:", err);
    }
  };

  const loadConfig = async () => {
    try {
      const resp = await fetch(`${backendOrigin}/config`);
      if (resp.ok) {
        const data = await resp.json();
        setConfig(data);
        setShowConfig(true);
      }
    } catch (err) {
      console.error("Failed to load config:", err);
    }
  };

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

    try {
      const resp = await fetch(`${backendOrigin}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          repoUrl, 
          fromRef, 
          toRef,
          githubToken: githubToken || null 
        }),
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

        const parts = buffer.split("\n\n");
        buffer = parts.pop();

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
      
      // Reload token usage after analysis
      await loadTokenUsage();
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
        {startupInfo && (
          <div className="startup-info">
            <small>
              📋 Config: {startupInfo.config_path}
              {startupInfo.github_token_configured && " | 🔑 GitHub token configured"}
            </small>
          </div>
        )}
      </header>

      {tokenUsage && (
        <div className={`token-usage-card ${tokenUsage.alert ? "alert" : ""}`}>
          <div className="token-usage-header">
            <span>📊 Token Usage</span>
            <button 
              className="config-btn" 
              onClick={loadConfig}
              title="View Configuration"
            >
              ⚙️
            </button>
          </div>
          <div className="token-usage-details">
            <div>
              Total: <strong aria-label="Total tokens used">{tokenUsage.usage.total_tokens.toLocaleString()}</strong> tokens
              (<span aria-label="Number of requests">{tokenUsage.usage.requests_count}</span> requests)
            </div>
            {tokenUsage.alert && (
              <div className="token-alert" role="alert">
                ⚠️ Usage at {tokenUsage.percentage}% of threshold
              </div>
            )}
          </div>
        </div>
      )}

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

        <label>
          GitHub Token (optional)
          <input
            type="password"
            placeholder="ghp_... (for private repos or rate limit increase)"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
          />
        </label>

        <button onClick={analyze} disabled={loading || !repoUrl || !fromRef || !toRef}>
          {loading ? "Analyzing…" : "🚀 Analyze Upgrade"}
        </button>
      </section>

      {showConfig && config && (
        <section className="config-card">
          <div className="config-header">
            <h3>⚙️ Configuration</h3>
            <button className="close-btn" onClick={() => setShowConfig(false)}>✕</button>
          </div>
          <div className="config-details">
            <div className="config-item">
              <span>GitHub Token:</span>
              <span>{config.github_token ? "Configured" : "Not set"}</span>
            </div>
            <div className="config-item">
              <span>Token Monitoring:</span>
              <span>{config.enable_token_monitoring ? "Enabled" : "Disabled"}</span>
            </div>
            <div className="config-item">
              <span>Token Threshold:</span>
              <span>{config.token_usage_threshold}%</span>
            </div>
            <div className="config-item">
              <span>Include Migration Paths:</span>
              <span>{config.include_migration_paths ? "Yes" : "No"}</span>
            </div>
            <div className="config-item">
              <span>Validate Upgrade Logic:</span>
              <span>{config.validate_upgrade_logic ? "Yes" : "No"}</span>
            </div>
          </div>
          <p className="config-note">
            💡 Edit <code>.upgradesage</code> file to customize settings
          </p>
        </section>
      )}

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
