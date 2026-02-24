# Pre-Commit Setup for Git Repository

**Note:** Pre-commit hooks require a Git repository. If not already initialized, run:

```bash
git init
git add .
git commit -m "Initial commit: add code style tooling"
```

## Install Pre-Commit Hooks

Once Git is initialized:

```bash
# Install hook framework
pre-commit install

# Verify installation
ls -la .git/hooks/  # Should see pre-commit hook installed

# (Optional) Run immediately on all files
pre-commit run --all-files
```

Once installed, **any future `git commit` will automatically run**:
- ✅ `black` — Auto-formats code
- ✅ `isort` — Auto-sorts imports
- ⚠️ `pycodestyle` — Style violations (prints warnings, doesn't block)
- ⚠️ `pylint` — Linting (prints warnings, doesn't block)
- ✅ `flake8` — General linting  
- ✅ `yamllint` — YAML validation
- ✅ Pre-commit hooks — Trailing whitespace, merge conflicts, large files

## What Happens on Commit

1. **Auto-fixable issues** (black, isort, trailing whitespace) → **automatically fixed**
2. **Warning-only issues** (pylint, pycodestyle) → **printed to console, doesn't block**
3. **Blocking issues** (merge conflicts, YAML syntax, files >5MB) → **commit fails until fixed**

## Example Workflow

```bash
# Edit code
vim src/strategies/new_strategy.py

# Stage changes
git add src/strategies/new_strategy.py

# Try to commit
git commit -m "Add new strategy"

# Pre-commit runs:
# - Reformats with black ✓
# - Sorts imports with isort ✓
# - Checks for issues...

# If auto-fixes applied:
# Commit fails! (Let you review auto-fixes)

# Re-stage (includes auto-fixed code) and try again
git add src/strategies/new_strategy.py
git commit -m "Add new strategy"

# Now commits successfully
```

## Bypass Hooks (Emergency Only)

```bash
git commit --no-verify -m "Skip pre-commit checks"
```

⚠️ **Discouraged** — loses automated safety. Use only if absolutely necessary.

## Uninstall Hooks

```bash
pre-commit uninstall
```

---

**Status:** Tooling installed. Awaiting Git initialization to activate pre-commit hooks.

See [CODE_STYLE_SETUP.md](CODE_STYLE_SETUP.md) for command reference.
