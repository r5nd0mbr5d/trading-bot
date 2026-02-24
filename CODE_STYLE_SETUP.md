# Code Style Setup & Quick Reference

**This project uses automated style enforcement via Black, Pylint, and pre-commit hooks.**

## One-Time Setup

Install tooling and activate pre-commit hooks:

```bash
pip install pre-commit black pylint pycodestyle isort yapf
pre-commit install
```

This installs hooks into `.git/hooks/`; they **run automatically on every commit**.

---

## Quick Commands

### Check styling (without modifying)
```bash
black --check src/ tests/ backtest/
```

### Auto-format all code
```bash
black src/ tests/ backtest/ research/scripts/
```

### Check linting warnings
```bash
pylint src/ --rcfile=.pylintrc --exit-zero
```

### Run pre-commit manually on all files
```bash
pre-commit run --all-files
```

### Run pre-commit only on changed files
```bash
pre-commit run
```

### Skip hooks on a specific commit (discouraged)
```bash
git commit --no-verify -m "message"
```

### Auto-format imports
```bash
isort src/ tests/
```

---

## What Gets Checked?

| Tool | What | Threshold |
|------|------|-----------|
| **black** | Code formatting | Auto-fixes (line length 100, no config needed) |
| **isort** | Import ordering | Auto-fixes (black-compatible) |
| **pycodestyle** | PEP 8 violations | Warnings printed, doesn't block commit |
| **pylint** | Naming, logic, metrics | Warnings printed (exit code 0; doesn't block) |
| **flake8** | General linting | Warnings printed, doesn't block commit |
| **yamllint** | YAML files | Auto-fails on invalid YAML |
| **pre-commit hooks** | Trailing whitespace, merge conflicts, large files | Auto-fixes or blocks |

---

## Key Rules (From Style Guide)

### Must Have
- ✅ Type hints on public functions: `def fetch(symbol: str) -> pd.DataFrame:`
- ✅ Docstrings on public classes/functions (NumPy style)
- ✅ Private methods prefixed with `_`: `def _validate()`
- ✅ UTC-aware timestamps: `pd.to_datetime(df.index, utc=True)`
- ✅ One statement per line
- ✅ Explicit function signatures (not `*args`/`**kwargs`)

### Avoid
- ❌ No multiple imports on one line: `import os, sys` (use 2 lines)
- ❌ No backslash line continuation (use parentheses instead)
- ❌ No compound statements: `if x: return y` (use 2 lines)
- ❌ No `eval()`, `exec()`, `__getattr__` magic
- ❌ No hardcoded symbols/dates (use `config/settings.py`)

---

## IDE Setup (VS Code)

### Extensions (recommended)
- **Python** (Microsoft)
- **Pylance** (Microsoft, type checking)
- **Black Formatter** (Microsoft)
- **Pylint** (Microsoft)
- **EditorConfig for VS Code** (EditorConfig Team)

### VS Code Settings (`.vscode/settings.json`)
Add to `.vscode/settings.json`:
```json
{
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.formatOnPaste": false,
    "editor.lineLength": 100
  },
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.pylintPath": "pylint"
}
```

---

## CI/CD Integration

If running in CI (GitHub Actions, GitLab CI, etc.):

```bash
# Fail if code is not formatted
black --check src/ tests/

# Fail if linting score is below 8
pylint src/ --rcfile=.pylintrc --fail-under=8

# Run tests
pytest tests/ -v
```

---

## Troubleshooting

### "pre-commit not found"
```bash
pip install pre-commit
pre-commit install
```

### "Black thinks my line is too long"
Either:
1. Shorten it
2. Use implicit line continuation (parentheses):
   ```python
   result = long_function(
       param1, param2, param3
   )
   ```

### "Pylint says 'missing-docstring'"
Add a docstring:
```python
def my_function(x: int) -> int:
    """Calculate something."""
    return x * 2
```

### "Import order changed by isort"
That's expected. Re-run `git status` and commit the changes; isort brought them to PEP 8 order.

### "Can't commit; pre-commit failed"
Fix the issues (usually Black auto-fixes them):
```bash
black src/ tests/
git add .
git commit -m "..."
```

### Disable a specific check
Edit `.pylintrc` to disable: add to `disable =` list under `[MESSAGES CONTROL]`.
Or inline in code: `# pylint: disable=missing-docstring`

---

## References

- **Style Guide:** [.python-style-guide.md](.python-style-guide.md)
- **Black Docs:** https://black.readthedocs.io/
- **PEP 8:** https://www.python.org/dev/peps/pep-0008/
- **PEP 20 (Zen of Python):** `python -c "import this"`
- **Pylint:** https://www.pylint.org/
- **Pre-commit:** https://pre-commit.com/

---

**Last Updated:** February 24, 2026
