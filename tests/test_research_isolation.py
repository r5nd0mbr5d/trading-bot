"""Guards against module-level research/runtime boundary violations."""

import ast
from pathlib import Path

RESEARCH_ROOT = Path(__file__).resolve().parents[1] / "research"


def _has_module_level_src_import(source: str) -> bool:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "src" or alias.name.startswith("src."):
                    return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "src" or module.startswith("src."):
                return True
    return False


def test_research_tree_has_no_module_level_src_imports():
    offenders: list[str] = []
    for path in RESEARCH_ROOT.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        if _has_module_level_src_import(source):
            offenders.append(str(path.relative_to(RESEARCH_ROOT.parents[0])))

    assert offenders == [], f"Module-level src imports found: {offenders}"


def test_src_import_detector_flags_module_level_violation():
    sample = "from src.risk.manager import RiskManager\n\n\ndef f():\n    return 1\n"
    assert _has_module_level_src_import(sample) is True
