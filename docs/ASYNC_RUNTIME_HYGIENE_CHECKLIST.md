# Async Runtime Hygiene Checklist (IBMCP-03)

Scope: integration-facing async execution paths (`src/cli/runtime.py`, `src/trading/loop.py`, `src/execution/ibkr_broker.py`).

## Enforceable Checks

Run:

```bash
python scripts/async_runtime_hygiene_check.py --root .
```

Fail conditions (inside `async def`):
- `time.sleep(...)`
- `requests.*`
- `subprocess.run(...)`

## Remediation Guidance

- Replace `time.sleep` with `await asyncio.sleep(...)`
- Use async-capable HTTP clients (`aiohttp` / async `httpx`) in async paths
- Replace blocking subprocess calls with `asyncio.create_subprocess_exec(...)` or move them to sync wrappers

## Operator Note

This check is static and conservative by design. A failure means an async path review is required before promotion.
