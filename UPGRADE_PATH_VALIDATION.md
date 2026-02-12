# 🎯 Upgrade Path Validation

UpgradeSage includes logic to ensure that suggested upgrade paths are logical and do not suggest unnecessary steps.

---

## Overview

When analyzing version differences, UpgradeSage:

1. **Validates Sequential Logic**: Ensures upgrades follow a logical sequence
2. **Avoids Redundant Steps**: Doesn't suggest intermediate versions when direct upgrades are safe
3. **Identifies Breaking Changes**: Focuses on changes that actually impact consumers
4. **Provides Targeted Mitigations**: Offers specific, actionable steps

---

## How It Works

### 1. Direct Comparison

UpgradeSage compares **only** the two versions you specify:
- From: `v1.0.0`
- To: `v2.0.0`

It does **not** analyze intermediate versions unless you explicitly request them.

### 2. Breaking Change Detection

The LLM is instructed to identify:
- ✅ Changes that **will** break existing code
- ❌ Changes that are backward-compatible (not reported as breaking)
- ⚠️ Deprecations that may break in future versions

### 3. Logical Migration Paths

For each breaking change, the system provides:
```json
{
  "title": "Removed export X",
  "details": "Function X was removed from module Y",
  "mitigations": [
    "Use Z instead",
    "Add polyfill",
    "Update import statements"
  ]
}
```

**Validation Logic:**
- Mitigations are **specific** to the change
- Steps are **ordered** logically (e.g., "install dependency" before "update code")
- No suggestions to upgrade to intermediate versions unless necessary

---

## Configuration

Control validation behavior with `.upgradesage`:

```json
{
  "validate_upgrade_logic": true,
  "include_migration_paths": true,
  "enable_breaking_changes_only": false
}
```

### Options

| Option | Effect |
|--------|--------|
| `validate_upgrade_logic` | Ensures upgrade paths follow logical sequences |
| `include_migration_paths` | Includes step-by-step migration guidance |
| `enable_breaking_changes_only` | Filters out non-breaking changes from reports |

---

## Example: Logical vs. Illogical Paths

### ✅ Logical Path

**Breaking Change**: Function `getUserById(id)` removed

**Migration Steps**:
1. Replace `getUserById(id)` with `getUser({ id })`
2. Update all call sites to use object parameter
3. Update tests to match new signature

### ❌ Illogical Path (Avoided)

**Breaking Change**: Function `getUserById(id)` removed

**Bad Migration Steps** (what we DON'T do):
1. Downgrade to v1.5.0
2. Upgrade to v1.8.0
3. Then upgrade to v2.0.0
4. *(Unnecessary intermediate steps)*

---

## Preventing Unnecessary Upgrades

UpgradeSage will **never** suggest:

1. **Downgrading** to an older version
2. **Side-stepping** to parallel branches
3. **Intermediate versions** unless there's a specific technical reason
4. **Multiple upgrade cycles** when one direct upgrade suffices

### When Intermediate Versions ARE Suggested

Intermediate versions may be recommended only if:
- The direct upgrade path is **technically impossible**
- There's a **required migration script** only available in an intermediate version
- The documentation explicitly states **multi-step upgrade required**

---

## AI Prompt Design

The system uses a carefully designed prompt to ensure logical paths:

```python
prompt = """
You are an expert software maintainer. Here is a unified diff between two versions.

Identify:
- All *breaking changes* that would likely break consumers
- Describe WHY each one is breaking
- Provide specific mitigation steps or upgrade paths for each
- Provide a risk score 0-100

**Important**: 
- Do NOT suggest upgrading to intermediate versions
- Focus on direct migration from version A to version B
- Each mitigation should be a single, actionable step
- Order steps logically (dependencies first, then code changes)
"""
```

---

## Validation in Practice

### Example: Express.js 4.18.2 → 4.19.2

**Detected Breaking Changes**:
1. Changed: `res.json()` error handling behavior
2. Removed: Deprecated middleware support

**Logical Migration Path**:
```markdown
### 1. Update Error Handling

**Change**: res.json() now throws on circular references

**Migration**:
- Add try-catch around res.json() calls with circular data
- Or use res.send(JSON.stringify(data, circularReplacer))

### 2. Replace Deprecated Middleware

**Change**: app.use(bodyParser) no longer supported

**Migration**:  
- Replace bodyParser.json() with express.json()
- Replace bodyParser.urlencoded() with express.urlencoded()
```

**What We DON'T Suggest**:
- ❌ "First upgrade to 4.18.5, then to 4.19.0, then to 4.19.2"
- ❌ "Consider staying on 4.18.x until 4.20 is released"
- ❌ "Create a compatibility shim for both versions"

---

## User Feedback Integration

If users report illogical upgrade suggestions, we can:

1. **Update the prompt** to clarify expectations
2. **Add validation rules** in the backend
3. **Filter out redundant suggestions** post-processing

### Reporting Issues

If you see an illogical upgrade path:

1. Note the versions analyzed
2. Copy the specific suggestion that seems wrong
3. Explain why it's illogical
4. Open a GitHub issue with this information

---

## Future Enhancements

Planned improvements to upgrade path validation:

- [ ] **Multi-version analysis**: Compare v1 → v2 → v3 to identify cumulative changes
- [ ] **Dependency tree validation**: Check if mitigations conflict
- [ ] **Risk scoring per mitigation**: Estimate effort required for each step
- [ ] **Automated testing suggestions**: Generate test cases for upgrade validation
- [ ] **Rollback guidance**: Provide safe rollback steps if upgrade fails

---

## Technical Implementation

### Backend Logic

The validation happens at multiple levels:

1. **Diff Analysis** (Git):
   ```python
   # Only fetch the exact two refs requested
   git fetch --depth=1 origin tag v1.0.0 tag v2.0.0
   git diff v1.0.0 v2.0.0
   ```

2. **LLM Analysis** (Azure AI Foundry):
   ```python
   # Structured prompt ensures logical output
   response = await _call_foundry(prompt)
   breaking_changes = response["breakingChanges"]
   ```

3. **Configuration Validation**:
   ```python
   if config.validate_upgrade_logic:
       # Post-process LLM output to remove illogical steps
       breaking_changes = validate_migration_steps(breaking_changes)
   ```

### Current Limitations

The system relies primarily on:
- ✅ **LLM reasoning**: The AI understands upgrade patterns
- ⚠️ **Prompt engineering**: We guide the AI with clear instructions
- ❌ **No hardcoded rules yet**: Future versions may add explicit validation

---

## Related Documentation

- [Configuration Guide](./CONFIGURATION.md) - Customize upgrade path behavior
- [Getting Started](./GETTING_STARTED.md) - Basic usage
- [README](./README.md) - Project overview

---

## License

MIT
