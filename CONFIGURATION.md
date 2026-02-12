# 🔧 Configuration Guide for UpgradeSage

UpgradeSage supports user-specific configuration through a `.upgradesage` file. This allows you to customize behavior without modifying code or environment variables.

---

## 📋 Quick Start

### 1. Create Your Configuration File

Copy the example configuration:

```bash
cp .upgradesage.example .upgradesage
```

### 2. Edit Settings

Open `.upgradesage` in your text editor and customize the values:

```json
{
  "github_token": null,
  "include_public_repos": true,
  "enable_token_monitoring": true,
  "token_usage_threshold": 80,
  "max_tokens_per_request": 120000,
  "enable_breaking_changes_only": false,
  "include_migration_paths": true,
  "validate_upgrade_logic": true,
  "show_startup_check": true
}
```

---

## ⚙️ Configuration Options

### GitHub Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `github_token` | string \| null | `null` | Optional GitHub personal access token for private repos or increased rate limits |
| `include_public_repos` | boolean | `true` | Include public repositories in analysis |

**GitHub Token Usage:**
- Set to `null` or omit for public repositories
- Provide a personal access token (PAT) for:
  - Private repository access
  - Higher API rate limits (5,000 vs 60 requests/hour)
  - Bypassing IP-based rate limiting

**How to get a GitHub token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Copy the token and add it to your `.upgradesage` file

---

### Token Usage Monitoring

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_token_monitoring` | boolean | `true` | Track and monitor LLM token usage |
| `token_usage_threshold` | integer | `80` | Alert when usage exceeds this percentage (0-100) |
| `max_tokens_per_request` | integer | `120000` | Maximum tokens to use per analysis request |

**Token Monitoring Features:**
- Tracks prompt and completion tokens across requests
- Shows real-time usage in the UI
- Alerts when usage exceeds your threshold
- Helps control costs with Azure AI Foundry

**Example Alert:**
```
⚠️ Token usage at 85.3% of configured threshold
```

---

### Analysis Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_breaking_changes_only` | boolean | `false` | Report only breaking changes (future feature) |
| `include_migration_paths` | boolean | `true` | Include suggested migration steps in reports |
| `validate_upgrade_logic` | boolean | `true` | Ensure upgrade paths are logical and sequential |

**Migration Paths:**
When enabled, the LLM will provide specific steps to migrate from one version to another:
- Detailed mitigation strategies
- Code examples when relevant
- Upgrade sequence validation

---

### Startup Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `show_startup_check` | boolean | `true` | Display configuration validation at analysis start |

**Startup Check Output:**
```
⚙️ Config: /home/user/project/.upgradesage | 🔑 GitHub token configured
```

---

## 📍 Configuration File Locations

UpgradeSage looks for `.upgradesage` in the following order:

1. **Current Directory**: `./upgradesage`
2. **Home Directory**: `~/.upgradesage`
3. **Defaults**: If no file is found, uses built-in defaults

### Team Deployments

For team projects, place `.upgradesage` in your project root:

```bash
project/
├── .upgradesage          # Team-specific settings
├── .upgradesage.example  # Template for new team members
├── .gitignore            # Excludes .upgradesage (already configured)
├── api/
└── web/
```

**Important:** `.upgradesage` is automatically excluded from version control to prevent committing sensitive tokens.

---

## 🔌 API Endpoints

The configuration system exposes several API endpoints:

### Get Current Configuration

```bash
curl http://localhost:8000/config
```

**Response:**
```json
{
  "github_token": null,
  "include_public_repos": true,
  "enable_token_monitoring": true,
  "token_usage_threshold": 80,
  ...
}
```

### Get Token Usage Statistics

```bash
curl http://localhost:8000/config/token-usage
```

**Response:**
```json
{
  "usage": {
    "prompt_tokens": 45200,
    "completion_tokens": 1850,
    "total_tokens": 47050,
    "requests_count": 3
  },
  "percentage": 39.21,
  "threshold": 80,
  "alert": false
}
```

### Get Startup Validation

```bash
curl http://localhost:8000/config/startup
```

**Response:**
```json
{
  "config_loaded": true,
  "config_path": "/home/user/project/.upgradesage",
  "github_token_configured": true,
  "token_monitoring_enabled": true,
  "settings": {
    "include_public_repos": true,
    "include_migration_paths": true,
    "validate_upgrade_logic": true
  }
}
```

---

## 💡 Best Practices

### Security

1. **Never commit `.upgradesage` with tokens** - it's already in `.gitignore`
2. **Use environment variables in CI/CD** - override config with `GITHUB_TOKEN` env var
3. **Rotate tokens regularly** - especially if shared across team members
4. **Use minimal token scopes** - only grant `repo` scope if needed

### Token Management

1. **Monitor usage regularly** - check the token usage card in the UI
2. **Set appropriate thresholds** - adjust `token_usage_threshold` based on your budget
3. **Optimize diff sizes** - smaller version jumps = fewer tokens
4. **Test with public repos first** - validate setup before using tokens

### Team Collaboration

1. **Share `.upgradesage.example`** - commit the template for team reference
2. **Document custom settings** - add comments in your example file
3. **Use consistent thresholds** - align token limits across the team
4. **Separate dev/prod configs** - different settings for different environments

---

## 🐛 Troubleshooting

### Configuration Not Loading

**Problem:** Changes to `.upgradesage` aren't reflected

**Solution:** Restart the FastAPI backend:
```bash
# Stop the server (Ctrl+C)
# Start it again
uvicorn main:app --reload --port 8000
```

### GitHub Token Not Working

**Problem:** Still getting rate limited despite token

**Solution:**
1. Verify token has `repo` scope
2. Check token hasn't expired
3. Ensure token is in config file or `GITHUB_TOKEN` env var
4. Test token with: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user`

### Token Usage Always at 0%

**Problem:** Token monitoring shows 0% usage

**Solution:**
- Token usage resets when backend restarts
- Only tracks usage for current session
- Perform an analysis to see usage update

### Invalid Configuration Error

**Problem:** Backend warns about invalid config

**Solution:**
1. Validate JSON syntax with `python -m json.tool .upgradesage`
2. Check all boolean values are `true` or `false` (lowercase)
3. Ensure `token_usage_threshold` is between 0-100
4. Verify all required fields are present

---

## 🔄 Environment Variable Priority

Configuration sources are loaded in this order (later sources override earlier):

1. **Default values** (built into `config.py`)
2. **`.upgradesage` file** (current or home directory)
3. **Environment variables** (`GITHUB_TOKEN` overrides config file token)

Example:
```bash
# Config file has github_token: null
# Environment variable overrides it
export GITHUB_TOKEN=ghp_abc123
uvicorn main:app --reload --port 8000
```

---

## 📊 Example Configurations

### Minimal (Public Repos Only)

```json
{
  "github_token": null,
  "enable_token_monitoring": true,
  "token_usage_threshold": 90,
  "show_startup_check": false
}
```

### Team with Private Repos

```json
{
  "github_token": "ghp_teamTokenHere",
  "enable_token_monitoring": true,
  "token_usage_threshold": 75,
  "include_migration_paths": true,
  "validate_upgrade_logic": true,
  "show_startup_check": true
}
```

### Cost-Conscious

```json
{
  "enable_token_monitoring": true,
  "token_usage_threshold": 60,
  "max_tokens_per_request": 80000,
  "enable_breaking_changes_only": true,
  "show_startup_check": true
}
```

---

## 📚 Related Documentation

- [Getting Started Guide](./GETTING_STARTED.md) - Setup and basic usage
- [README](./README.md) - Project overview
- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-services/) - LLM provider info

---

## 🆘 Need Help?

If you encounter issues:

1. Check the [Troubleshooting](#-troubleshooting) section above
2. Review backend logs for specific error messages
3. Validate your config with JSON linter
4. Open an issue on GitHub with:
   - Your `.upgradesage` file (redact tokens!)
   - Backend error logs
   - Steps to reproduce

---

## License

MIT
