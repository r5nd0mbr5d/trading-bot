"""Classify trading-bot user prompts into PAIOS session types.

Uses priority-ordered keyword heuristics to map a free-text prompt to
the most appropriate ``SessionType``.  Defaults to ``SessionType.IMPL``
when no keyword category matches.
"""

from src.bridge.paios_types import SessionType

_OPS_KEYWORDS = ("deploy", "ci", "docker", "config", "environment", "setup")
_DEBUG_KEYWORDS = ("bug", "error", "crash", "debug", "fix", "broken", "fail")
_REVIEW_KEYWORDS = ("review", "audit", "check", "validate", "approve")
_RSRCH_KEYWORDS = ("research", "backtest", "analyze", "compare", "study", "investigate")
_ARCH_KEYWORDS = ("architecture", "design", "refactor", "restructure", "pipeline", "pattern")


def classify_prompt(prompt: str) -> SessionType:
    """Classify a trading-bot user prompt into a session type.

    Uses priority-ordered keyword matching so that more operationally
    critical session types (OPS, DEBUG) take precedence over broader
    categories (RSRCH, ARCH).  Falls back to ``SessionType.IMPL`` when
    no keyword matches.

    Parameters
    ----------
    prompt : str
        Free-text user prompt describing the desired session task.

    Returns
    -------
    SessionType
        The best-matching session type for the given prompt.
    """
    prompt_lower = prompt.lower()

    if any(kw in prompt_lower for kw in _OPS_KEYWORDS):
        return SessionType.OPS
    if any(kw in prompt_lower for kw in _DEBUG_KEYWORDS):
        return SessionType.DEBUG
    if any(kw in prompt_lower for kw in _REVIEW_KEYWORDS):
        return SessionType.REVIEW
    if any(kw in prompt_lower for kw in _RSRCH_KEYWORDS):
        return SessionType.RSRCH
    if any(kw in prompt_lower for kw in _ARCH_KEYWORDS):
        return SessionType.ARCH
    return SessionType.IMPL
